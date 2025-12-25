"""UIBridge - Core event bridge implementation.

The UIBridge transforms Amplifier events into UIEvents and routes
them through the configured adapter. It supports:
- Event filtering by pattern
- Custom event handlers
- Event transformation pipeline
- Bidirectional command handling
"""

from __future__ import annotations

import fnmatch
import logging
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from .schema import EventTypes, UIEvent

logger = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Configuration presets
PRESETS = {
    "minimal": ["tool:post", "error:*"],
    "standard": ["session:*", "content_block:*", "tool:*", "token_usage"],
    "verbose": ["*"],
    "debug": ["*"],
}

DEFAULT_CONFIG: dict[str, Any] = {
    "events": PRESETS["standard"],
    "preset": None,
    "display": {
        "show_thinking": True,
        "show_tool_arguments": True,
        "show_tool_output": True,
        "truncate_output": 500,
        "include_timestamps": True,
        "include_duration": True,
    },
    "agents": {
        "parse_agent_names": True,
        "indent_sub_agents": True,
    },
    "history": {
        "enabled": False,
        "max_events": 1000,
    },
}


class UIBridge:
    """Core bridge that transforms Amplifier events to UIEvents.
    
    The UIBridge:
    1. Receives Amplifier events (tool:pre, content_block:end, etc.)
    2. Transforms them into UIEvent objects
    3. Applies filters and transformers
    4. Emits through the configured adapter
    
    Attributes:
        config: Bridge configuration
        adapter: Transport adapter (Queue, Tauri, WebSocket, etc.)
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the UI bridge.
        
        Args:
            config: Configuration dict (merged with defaults)
        """
        # Deep merge with defaults
        self.config = _deep_merge(DEFAULT_CONFIG, config or {})
        
        # Apply preset if specified
        if self.config.get("preset"):
            preset_name = self.config["preset"]
            if preset_name in PRESETS:
                self.config["events"] = PRESETS[preset_name]
        
        # Internal state
        self._thinking_events: dict[int, str] = {}  # block_index -> event_id
        self._tool_events: dict[str, tuple[str, datetime]] = {}  # tool_name -> (event_id, start)
        self._filters: list[Callable[[UIEvent], bool]] = []
        self._transformers: list[Callable[[UIEvent], UIEvent]] = []
        self._handlers: dict[str, list[Callable]] = {}
        self._command_handlers: dict[str, Callable] = {}
        self._history: list[UIEvent] = []
        self._adapter = None
    
    def set_adapter(self, adapter) -> None:
        """Set the transport adapter.
        
        Args:
            adapter: UIAdapter instance
        """
        self._adapter = adapter
    
    # ─────────────────────────────────────────────────────────────────────────
    # Handler Registration
    # ─────────────────────────────────────────────────────────────────────────
    
    def on(self, event_pattern: str):
        """Decorator to register an event handler.
        
        Args:
            event_pattern: Event name or glob pattern (e.g., "tool:*")
        
        Example:
            @bridge.on("tool:post")
            async def my_handler(event_name, data, bridge):
                data["custom_field"] = "value"
                return bridge.default_handler(event_name, data)
        """
        def decorator(fn: Callable) -> Callable:
            if event_pattern not in self._handlers:
                self._handlers[event_pattern] = []
            self._handlers[event_pattern].append(fn)
            return fn
        return decorator
    
    def off(self, event_pattern: str, handler: Callable) -> None:
        """Unregister an event handler.
        
        Args:
            event_pattern: Pattern the handler was registered with
            handler: The handler function to remove
        """
        if event_pattern in self._handlers:
            self._handlers[event_pattern] = [
                h for h in self._handlers[event_pattern] if h != handler
            ]
    
    def on_command(self, command_type: str):
        """Decorator to register a command handler.
        
        Args:
            command_type: Command type to handle
        
        Example:
            @bridge.on_command("submit_prompt")
            async def handle_prompt(data):
                prompt = data["prompt"]
                await orchestrator.execute(prompt)
        """
        def decorator(fn: Callable) -> Callable:
            self._command_handlers[command_type] = fn
            return fn
        return decorator
    
    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline Customization
    # ─────────────────────────────────────────────────────────────────────────
    
    def filter(self, fn: Callable[[UIEvent], bool]) -> Callable:
        """Add a filter to the event pipeline.
        
        Return False to drop the event, True to keep it.
        
        Example:
            @bridge.filter
            def drop_thinking(event):
                return event.type != "thinking_start"
        """
        self._filters.append(fn)
        return fn
    
    def transform(self, fn: Callable[[UIEvent], UIEvent]) -> Callable:
        """Add a transformer to the event pipeline.
        
        Example:
            @bridge.transform
            def add_metadata(event):
                event.data["app_version"] = "1.0.0"
                return event
        """
        self._transformers.append(fn)
        return fn
    
    # ─────────────────────────────────────────────────────────────────────────
    # Event Handling
    # ─────────────────────────────────────────────────────────────────────────
    
    async def handle_event(self, event_name: str, data: dict[str, Any]) -> UIEvent | None:
        """Handle an Amplifier event and emit UIEvent(s).
        
        Args:
            event_name: Amplifier event name (e.g., "tool:pre")
            data: Event data from Amplifier
            
        Returns:
            The emitted UIEvent, or None if filtered/skipped
        """
        # Check if event matches our filter patterns
        if not self._should_handle(event_name):
            return None
        
        # Find matching handlers (custom first, then default)
        handlers = self._get_matching_handlers(event_name)
        
        ui_event = None
        for handler in handlers:
            try:
                result = await handler(event_name, data, self)
                if result is not None:
                    ui_event = result
                    break
            except Exception as e:
                logger.error(f"Handler error for {event_name}: {e}")
        
        # Fall back to default handler
        if ui_event is None:
            ui_event = self.default_handler(event_name, data)
        
        if ui_event is None:
            return None
        
        # Apply filters
        for f in self._filters:
            try:
                if not f(ui_event):
                    return None
            except Exception as e:
                logger.error(f"Filter error: {e}")
        
        # Apply transformers
        for t in self._transformers:
            try:
                ui_event = t(ui_event)
            except Exception as e:
                logger.error(f"Transformer error: {e}")
        
        # Emit
        await self.emit(ui_event)
        return ui_event
    
    def _should_handle(self, event_name: str) -> bool:
        """Check if event matches configured patterns."""
        patterns = self.config.get("events", ["*"])
        for pattern in patterns:
            if fnmatch.fnmatch(event_name, pattern):
                return True
        return False
    
    def _get_matching_handlers(self, event_name: str) -> list[Callable]:
        """Get handlers that match the event name."""
        handlers = []
        for pattern, pattern_handlers in self._handlers.items():
            if fnmatch.fnmatch(event_name, pattern):
                handlers.extend(pattern_handlers)
        return handlers
    
    # ─────────────────────────────────────────────────────────────────────────
    # Default Handlers
    # ─────────────────────────────────────────────────────────────────────────
    
    def default_handler(self, event_name: str, data: dict[str, Any]) -> UIEvent | None:
        """Create default UIEvent for an Amplifier event.
        
        Args:
            event_name: Amplifier event name
            data: Event data
            
        Returns:
            UIEvent or None if event should be skipped
        """
        display = self.config.get("display", {})
        agents = self.config.get("agents", {})
        
        # Parse agent name from session_id
        agent_name = None
        if agents.get("parse_agent_names"):
            agent_name = self._parse_agent_name(data.get("session_id"))
        
        session_id = data.get("session_id")
        
        match event_name:
            case "session:start":
                return UIEvent(
                    type=EventTypes.SESSION_START,
                    timestamp=datetime.now(),
                    data={"prompt": data.get("prompt", "")},
                    session_id=session_id,
                )
            
            case "session:end":
                return UIEvent(
                    type=EventTypes.SESSION_END,
                    timestamp=datetime.now(),
                    data=data,
                    session_id=session_id,
                )
            
            case "content_block:start":
                block_type = data.get("block_type")
                block_index = data.get("block_index")
                
                if block_type in {"thinking", "reasoning"} and display.get("show_thinking"):
                    event_id = str(uuid4())
                    self._thinking_events[block_index] = event_id
                    
                    return UIEvent(
                        type=EventTypes.THINKING_START,
                        timestamp=datetime.now(),
                        data={"block_index": block_index},
                        event_id=event_id,
                        session_id=session_id,
                        agent_name=agent_name,
                    )
                return None
            
            case "content_block:end":
                block_index = data.get("block_index")
                block = data.get("block", {})
                block_type = block.get("type")
                usage = data.get("usage")

                # Handle thinking block end
                if block_type in {"thinking", "reasoning"} and display.get("show_thinking"):
                    parent_id = self._thinking_events.pop(block_index, None)
                    thinking_text = block.get("thinking", "") or block.get("text", "")

                    event = UIEvent(
                        type=EventTypes.THINKING_END,
                        timestamp=datetime.now(),
                        data={
                            "block_index": block_index,
                            "content": thinking_text,
                        },
                        parent_event_id=parent_id,
                        session_id=session_id,
                        agent_name=agent_name,
                    )

                    # Also emit token usage if present
                    if usage:
                        # Schedule token usage event
                        import asyncio
                        asyncio.create_task(self.emit(UIEvent(
                            type=EventTypes.TOKEN_USAGE,
                            timestamp=datetime.now(),
                            data={
                                "input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                            },
                            session_id=session_id,
                            agent_name=agent_name,
                        )))

                    return event

                # Note: TEXT blocks are NOT converted to MESSAGE_END here.
                # MESSAGE_END is emitted by the message:end handler which receives
                # the canonical event from the orchestrator with the complete response.
                # This avoids duplicates and fragmentation from per-block events.

                # Token usage on non-thinking blocks
                if usage:
                    return UIEvent(
                        type=EventTypes.TOKEN_USAGE,
                        timestamp=datetime.now(),
                        data={
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                        },
                        session_id=session_id,
                        agent_name=agent_name,
                    )

                return None
            
            case "tool:pre":
                tool_name = data.get("tool_name", "unknown")
                event_id = str(uuid4())
                self._tool_events[tool_name] = (event_id, datetime.now())
                
                event_data: dict[str, Any] = {"tool_name": tool_name}
                if display.get("show_tool_arguments"):
                    args = data.get("tool_input", {})
                    event_data["arguments"] = self._truncate(str(args))
                
                return UIEvent(
                    type=EventTypes.TOOL_START,
                    timestamp=datetime.now(),
                    data=event_data,
                    event_id=event_id,
                    session_id=session_id,
                    agent_name=agent_name,
                )
            
            case "tool:post":
                tool_name = data.get("tool_name", "unknown")
                parent_id, start_time = self._tool_events.pop(tool_name, (None, None))

                result = data.get("tool_response", data.get("result", {}))
                success = True
                output = ""

                if isinstance(result, dict):
                    success = result.get("success", True)
                    output = str(result.get("output", result))
                else:
                    output = str(result)

                # Start with any custom fields from data (for custom handlers)
                # Exclude known Amplifier fields
                known_fields = {"tool_name", "tool_response", "result", "tool_input", "session_id"}
                event_data = {k: v for k, v in data.items() if k not in known_fields}

                # Add standard fields
                event_data["tool_name"] = tool_name
                event_data["success"] = success

                if display.get("show_tool_output"):
                    event_data["output"] = self._truncate(output)

                if display.get("include_duration") and start_time:
                    duration = (datetime.now() - start_time).total_seconds()
                    event_data["duration_ms"] = int(duration * 1000)

                return UIEvent(
                    type=EventTypes.TOOL_RESULT,
                    timestamp=datetime.now(),
                    data=event_data,
                    parent_event_id=parent_id,
                    session_id=session_id,
                    agent_name=agent_name,
                )

            case "orchestrator:complete":
                # Canonical event from orchestrator with complete assistant response
                # This is the single source of truth for MESSAGE_END (no duplicates)
                # Uses the standard Amplifier event instead of custom message:end
                content = data.get("content", "")
                if content:
                    return UIEvent(
                        type=EventTypes.MESSAGE_END,
                        timestamp=datetime.now(),
                        data={
                            "content": content,
                            "role": data.get("role", "assistant"),
                            "turn_count": data.get("turn_count"),
                            "status": data.get("status"),
                            "orchestrator": data.get("orchestrator"),
                        },
                        session_id=session_id,
                        agent_name=agent_name,
                    )
                return None

            case _:
                # Handle error events
                if event_name.startswith("error"):
                    return UIEvent(
                        type=EventTypes.ERROR,
                        timestamp=datetime.now(),
                        data=data,
                        session_id=session_id,
                        agent_name=agent_name,
                    )
                return None
    
    def _parse_agent_name(self, session_id: str | None) -> str | None:
        """Extract agent name from hierarchical session ID."""
        if session_id and "_" in session_id:
            return session_id.split("_", 1)[1]
        return None
    
    def _truncate(self, text: str) -> str:
        """Truncate text based on config."""
        max_len = self.config.get("display", {}).get("truncate_output", 500)
        if max_len and len(text) > max_len:
            return text[:max_len] + f"... ({len(text) - max_len} more chars)"
        return text
    
    # ─────────────────────────────────────────────────────────────────────────
    # Event Emission
    # ─────────────────────────────────────────────────────────────────────────
    
    async def emit(self, event: UIEvent) -> None:
        """Emit a UIEvent through the adapter.
        
        Args:
            event: UIEvent to emit
        """
        # Store in history if enabled
        if self.config.get("history", {}).get("enabled"):
            max_events = self.config["history"].get("max_events", 1000)
            self._history.append(event)
            if len(self._history) > max_events:
                self._history = self._history[-max_events:]
        
        # Emit through adapter
        if self._adapter:
            await self._adapter.emit(event)
    
    async def handle_command(self, command) -> Any:
        """Handle a command from the UI.
        
        Args:
            command: UICommand to handle
            
        Returns:
            Result from the command handler
        """
        handler = self._command_handlers.get(command.type)
        if handler:
            return await handler(command.data)
        raise ValueError(f"Unknown command type: {command.type}")
    
    @property
    def event_history(self) -> list[UIEvent]:
        """Get event history (if enabled)."""
        return self._history.copy()
    
    async def replay(self, events: list[UIEvent]) -> None:
        """Replay a list of events through the adapter.
        
        Args:
            events: Events to replay
        """
        for event in events:
            await self.emit(event)
