"""
amplifier-module-hooks-ui-bridge: Universal Event Bridge for Any UI

This module bridges Amplifier events to any UI system (Textual, Tauri, Web, etc.)
with three levels of customization:
1. Configuration - profile.toml settings (event_mode, preset, display options)
2. Composition - Custom handlers and enrichers alongside defaults
3. Extension - Custom adapters for any output target

Event Modes:
    - "native": Pass-through amplifier-core event names (content_block:delta, tool:pre)
    - "ui_friendly": Semantic UI events (thinking_start, tool_result) - default
    - "both": Emit both native and ui_friendly events

Usage:
    # In profile.toml
    [[hooks]]
    module = "hooks-ui-bridge"
    name = "ui-bridge"
    
    [hooks.config]
    event_mode = "native"  # or "ui_friendly" (default), "both"
    
    [hooks.config.transport]
    type = "queue"  # or "tauri", "websocket"
    
    # In your TUI app
    from amplifier_module_hooks_ui_bridge import create_queue_adapter
    queue = create_queue_adapter()
    # ... consume from queue.event_queue in your Textual app
"""

__amplifier_module_type__ = "hook"
__version__ = "0.2.0"

import logging
from typing import Any, Callable

from amplifier_core.models import HookResult

from .adapters import (
    MockAdapter,
    QueueAdapter,
    TauriIPCAdapter,
    UIAdapter,
    WebSocketAdapter,
)
from .bridge import UIBridge
from .events import NativeEventTypes, UIEventTypes
from .forwarder import BatchEventForwarder, EventForwarder
from .schema import CommandTypes, UICommand, UIEvent

# Backwards compatibility: EventTypes is alias for UIEventTypes
EventTypes = UIEventTypes

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Global State
# ═══════════════════════════════════════════════════════════════════════════════

_bridge: UIBridge | None = None
_adapters: dict[str, UIAdapter] = {}
_custom_handlers: dict[str, list[Callable]] = {}
_custom_enrichers: list[tuple[str, Callable]] = []


def get_bridge() -> UIBridge | None:
    """Get the bridge instance (available after mount)."""
    return _bridge


def set_adapter(adapter: UIAdapter, name: str = "default") -> None:
    """Set a custom adapter.
    
    Args:
        adapter: UIAdapter instance
        name: Adapter name (for multi-adapter setups)
    """
    _adapters[name] = adapter


def get_adapter(name: str = "default") -> UIAdapter | None:
    """Get an adapter by name.
    
    Args:
        name: Adapter name
        
    Returns:
        UIAdapter or None
    """
    return _adapters.get(name)


# ═══════════════════════════════════════════════════════════════════════════════
# Queue Adapter Convenience
# ═══════════════════════════════════════════════════════════════════════════════

def create_queue_adapter(name: str = "default", maxsize: int = 1000) -> QueueAdapter:
    """Create and register a queue adapter.
    
    This is the main entry point for Textual TUI apps.
    
    Args:
        name: Adapter name
        maxsize: Maximum queue size
        
    Returns:
        QueueAdapter instance
        
    Example:
        adapter = create_queue_adapter()
        
        # In your Textual app
        async def consume():
            while True:
                event = await adapter.event_queue.get()
                handle_event(event)
    """
    adapter = QueueAdapter(name=name, maxsize=maxsize)
    _adapters[name] = adapter
    return adapter


# ═══════════════════════════════════════════════════════════════════════════════
# Handler Registration (Global)
# ═══════════════════════════════════════════════════════════════════════════════

def register_handler(event_pattern: str):
    """Decorator to register a custom event handler.
    
    Handlers intercept events BEFORE the default handler runs.
    Return a UIEvent to override, or None to fall back to default.
    Handlers registered before mount() are automatically added to the bridge.
    
    Args:
        event_pattern: Event name or glob pattern (e.g., "tool:*")
    
    Example:
        @register_handler("tool:post")
        async def add_badge(event_name, data, bridge):
            data["badge"] = "⚡" if data.get("duration", 0) < 1 else ""
            return bridge.default_handler(event_name, data)
    """
    def decorator(fn: Callable) -> Callable:
        if event_pattern not in _custom_handlers:
            _custom_handlers[event_pattern] = []
        _custom_handlers[event_pattern].append(fn)
        return fn
    return decorator


def register_enricher(event_pattern: str):
    """Decorator to register an event enricher.
    
    Enrichers run AFTER the default handler and can emit additional events.
    Use this for app-specific events (e.g., todo_update for amplifier-desktop).
    Enrichers registered before mount() are automatically added to the bridge.
    
    Args:
        event_pattern: Event name or glob pattern (e.g., "tool:post")
    
    Example:
        @register_enricher("tool:post")
        async def todo_enricher(event_name: str, data: dict, ui_event: UIEvent) -> list[UIEvent]:
            if data.get("tool_name") != "todo":
                return []
            return [UIEvent(
                type="todo_update",
                timestamp=datetime.now(),
                data={"todos": parse_todos(data)},
                session_id=ui_event.session_id,
            )]
    """
    def decorator(fn: Callable) -> Callable:
        _custom_enrichers.append((event_pattern, fn))
        return fn
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Custom Event Emission
# ═══════════════════════════════════════════════════════════════════════════════

async def emit_custom_event(event_type: str, data: dict[str, Any]) -> None:
    """Emit a custom event to the UI.
    
    Use this to emit application-specific events.
    
    Args:
        event_type: Your custom event type (e.g., "notification")
        data: Event data payload
        
    Example:
        await emit_custom_event("notification", {
            "message": "Build complete!",
            "level": "success"
        })
    """
    from datetime import datetime
    
    if _bridge:
        await _bridge.emit(UIEvent(
            type=event_type,
            timestamp=datetime.now(),
            data=data,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# Module Mount
# ═══════════════════════════════════════════════════════════════════════════════

async def mount(coordinator: Any, config: dict[str, Any]) -> None:
    """Mount the UI bridge hook module.
    
    This is called by Amplifier when the module is loaded.
    
    Args:
        coordinator: Amplifier coordinator
        config: Module configuration from profile.toml
    """
    global _bridge
    
    # Create bridge instance
    _bridge = UIBridge(config)
    
    # Add any pre-registered handlers
    for pattern, handlers in _custom_handlers.items():
        for handler in handlers:
            if pattern not in _bridge._handlers:
                _bridge._handlers[pattern] = []
            _bridge._handlers[pattern].append(handler)
    
    # Add any pre-registered enrichers
    for pattern, enricher in _custom_enrichers:
        _bridge._enrichers.append((pattern, enricher))
    
    # Load custom handlers module if configured
    custom_handlers_module = config.get("custom_handlers")
    if custom_handlers_module:
        try:
            import importlib
            importlib.import_module(custom_handlers_module)
            logger.info(f"Loaded custom handlers from {custom_handlers_module}")
        except ImportError as e:
            logger.error(f"Failed to load custom handlers: {e}")
    
    # Create/configure adapter based on transport config
    transport = config.get("transport", {})
    transport_type = transport.get("type", "queue")
    
    adapter: UIAdapter | None = None
    
    match transport_type:
        case "queue":
            queue_name = transport.get("queue_name", "default")
            maxsize = transport.get("max_queue_size", 1000)
            if queue_name not in _adapters:
                adapter = QueueAdapter(name=queue_name, maxsize=maxsize)
                _adapters[queue_name] = adapter
            else:
                adapter = _adapters[queue_name]
        
        case "tauri":
            adapter = TauriIPCAdapter()
            _adapters["tauri"] = adapter
        
        case "websocket":
            host = transport.get("host", "localhost")
            port = transport.get("port", 8765)
            adapter = WebSocketAdapter(host=host, port=port)
            _adapters["websocket"] = adapter
        
        case "custom":
            adapter_path = transport.get("adapter")
            if adapter_path:
                try:
                    module_path, class_name = adapter_path.rsplit(":", 1)
                    import importlib
                    module = importlib.import_module(module_path)
                    adapter_class = getattr(module, class_name)
                    adapter_config = transport.get("adapter_config", {})
                    adapter = adapter_class(**adapter_config)
                    _adapters["custom"] = adapter
                except Exception as e:
                    logger.error(f"Failed to load custom adapter: {e}")
    
    # Connect adapter
    if adapter:
        await adapter.connect()
        _bridge.set_adapter(adapter)
    
    # Register hook handlers with coordinator
    async def on_session_start(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("session:start", data)
        return HookResult(action="continue")
    
    async def on_session_end(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("session:end", data)
        return HookResult(action="continue")
    
    async def on_content_block_start(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("content_block:start", data)
        return HookResult(action="continue")
    
    async def on_content_block_delta(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("content_block:delta", data)
        return HookResult(action="continue")
    
    async def on_content_block_end(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("content_block:end", data)
        return HookResult(action="continue")
    
    async def on_thinking_delta(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("thinking:delta", data)
        return HookResult(action="continue")
    
    async def on_tool_pre(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("tool:pre", data)
        return HookResult(action="continue")
    
    async def on_tool_post(event: str, data: dict) -> HookResult:
        await _bridge.handle_event("tool:post", data)
        return HookResult(action="continue")

    async def on_orchestrator_complete(event: str, data: dict) -> HookResult:
        """Handle orchestrator:complete event with complete response content."""
        await _bridge.handle_event("orchestrator:complete", data)
        return HookResult(action="continue")

    # Register handlers
    coordinator.hooks.register("session:start", on_session_start)
    coordinator.hooks.register("session:end", on_session_end)
    coordinator.hooks.register("content_block:start", on_content_block_start)
    coordinator.hooks.register("content_block:delta", on_content_block_delta)
    coordinator.hooks.register("content_block:end", on_content_block_end)
    coordinator.hooks.register("thinking:delta", on_thinking_delta)
    coordinator.hooks.register("tool:pre", on_tool_pre)
    coordinator.hooks.register("tool:post", on_tool_post)
    coordinator.hooks.register("orchestrator:complete", on_orchestrator_complete)

    logger.info(f"Mounted hooks-ui-bridge v{__version__} with {transport_type} transport (event_mode={_bridge.event_mode})")


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Schema
    "UIEvent",
    "UICommand",
    "CommandTypes",
    
    # Event Types
    "EventTypes",       # Alias for UIEventTypes (backwards compatibility)
    "UIEventTypes",     # UI-friendly event types
    "NativeEventTypes", # Native amplifier-core event types
    
    # Adapters
    "UIAdapter",
    "QueueAdapter",
    "TauriIPCAdapter",
    "WebSocketAdapter",
    "MockAdapter",
    
    # Bridge
    "UIBridge",
    
    # Forwarder
    "EventForwarder",
    "BatchEventForwarder",
    
    # Global functions
    "get_bridge",
    "set_adapter",
    "get_adapter",
    "create_queue_adapter",
    "register_handler",
    "register_enricher",
    "emit_custom_event",
    
    # Mount
    "mount",
]
