# amplifier-module-hooks-ui-bridge

Universal event bridge for any UI system - Textual TUI, Tauri Desktop/Mobile, Web Dashboard, VS Code.

## Overview

`hooks-ui-bridge` transforms Amplifier events into a universal, JSON-serializable format that can be consumed by any UI system. It supports bidirectional communication, allowing UIs to send commands back to Amplifier.

```
Amplifier Events ──► UIEvent (JSON) ──► Transport Adapters ──► Any UI
                                    ◄── UICommand (back) ◄──
```

## Installation

```bash
# From git
amplifier module add git+https://github.com/michaeljabbour/amplifier-module-hooks-ui-bridge

# Or with uv
uv add amplifier-module-hooks-ui-bridge
```

## Quick Start

### Profile Configuration

```toml
[[hooks]]
module = "hooks-ui-bridge"

[hooks.config]
preset = "standard"
event_mode = "native"  # or "ui_friendly" (default), "both"

[hooks.config.transport]
type = "queue"  # For Textual TUI
```

### Event Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `ui_friendly` | Semantic events (`thinking_start`, `tool_result`) | Simple TUIs |
| `native` | Pass-through amplifier-core events (`content_block:delta`, `tool:pre`) | Sophisticated UIs like amplifier-desktop |
| `both` | Emit both event types | Migration, debugging |

### Textual TUI Integration

```python
from amplifier_module_hooks_ui_bridge import create_queue_adapter

# Create adapter
adapter = create_queue_adapter()

# Your Textual app consumes from the queue
async def consume_events():
    while True:
        event = await adapter.event_queue.get()
        # Handle event in your UI
        match event.type:
            case "tool_start":
                show_tool_spinner(event.data["tool_name"])
            case "tool_result":
                hide_tool_spinner(event.data["tool_name"])
```

### amplifier-desktop Integration (Native Mode)

For sophisticated UIs that need streaming deltas and fine-grained control:

```python
from amplifier_module_hooks_ui_bridge import (
    UIBridge, 
    QueueAdapter, 
    EventForwarder,
    NativeEventTypes,
)

# Create bridge with native mode
bridge = UIBridge(config={"event_mode": "native"})
adapter = QueueAdapter()
bridge.set_adapter(adapter)

# Forward events to WebSocket
async def send_to_websocket(event_dict: dict):
    event_dict["conversationId"] = conversation_id
    await websocket.send_json(event_dict)

forwarder = EventForwarder(adapter, send_to_websocket)
asyncio.create_task(forwarder.run())

# Handle streaming events
match event.type:
    case NativeEventTypes.CONTENT_BLOCK_DELTA:
        append_text(event.data["content"])
    case NativeEventTypes.TOOL_PRE:
        show_tool_call(event.data["tool_name"], event.data["tool_input"])
```

### Tauri Desktop Sidecar

```toml
# profile.toml
[hooks.config.transport]
type = "tauri"
```

Events are written to stdout as JSON lines. Commands are read from stdin.

## Transport Adapters

| Adapter | Transport | Use Case |
|---------|-----------|----------|
| `QueueAdapter` | asyncio.Queue | Textual TUI, In-process |
| `TauriIPCAdapter` | stdin/stdout | Desktop/Mobile sidecar |
| `WebSocketAdapter` | WebSocket | Web Dashboard |
| `MockAdapter` | In-memory | Testing |

## Event Types

### UI-Friendly Mode (default)

| Type | Description |
|------|-------------|
| `session_start` | Prompt submitted |
| `session_end` | Turn complete |
| `thinking_start` | Extended thinking begins |
| `thinking_end` | Extended thinking with content |
| `tool_start` | Tool invocation |
| `tool_result` | Tool completion |
| `message_end` | Complete assistant response |
| `token_usage` | Token counts |
| `error` | Errors |

### Native Mode

| Type | Description |
|------|-------------|
| `session:start` | Session start |
| `session:end` | Session end |
| `content_block:start` | Content block starts |
| `content_block:delta` | Streaming text/thinking chunk |
| `content_block:end` | Content block ends |
| `thinking:delta` | Thinking text chunk |
| `tool:pre` | Tool about to execute |
| `tool:post` | Tool completed |
| `orchestrator:complete` | Turn complete with full response |
| `error` | Errors |

## UIEvent Schema

```python
@dataclass
class UIEvent:
    type: str                           # Event type
    timestamp: datetime                 # When it occurred
    data: dict[str, Any]               # Event payload
    event_id: str                      # Unique ID
    parent_event_id: str | None        # For correlating start/end
    session_id: str | None             # Amplifier session ID
    conversation_id: str | None        # UI conversation thread (NEW)
    agent_name: str | None             # Sub-agent name
    hints: dict[str, Any] | None       # Platform hints
```

## Command Types

| Type | Description |
|------|-------------|
| `submit_prompt` | Send user message |
| `cancel_generation` | Cancel current generation |
| `switch_session` | Switch active session |

## Customization

### Level 1: Configuration

```toml
[hooks.config]
preset = "verbose"
event_mode = "native"

[hooks.config.display]
show_thinking = false
truncate_output = 1000
```

### Level 2: Custom Handlers

Handlers intercept events BEFORE the default handler:

```python
from amplifier_module_hooks_ui_bridge import register_handler

@register_handler("tool:post")
async def add_badge(event_name, data, bridge):
    data["badge"] = "⚡" if data.get("duration", 0) < 1 else ""
    return bridge.default_handler(event_name, data)
```

### Level 3: Event Enrichers (NEW)

Enrichers run AFTER the default handler and can emit additional events:

```python
from amplifier_module_hooks_ui_bridge import register_enricher, UIEvent
from datetime import datetime

@register_enricher("tool:post")
async def todo_enricher(event_name: str, data: dict, ui_event: UIEvent) -> list[UIEvent]:
    """Emit custom todo_update events for the todo tool."""
    if data.get("tool_name") != "todo":
        return []
    
    return [UIEvent(
        type="todo_update",
        timestamp=datetime.now(),
        data={"todos": parse_todos(data)},
        session_id=ui_event.session_id,
        conversation_id=ui_event.conversation_id,
    )]
```

### Level 4: Custom Adapters

```python
from amplifier_module_hooks_ui_bridge import UIAdapter, set_adapter

class MyAdapter(UIAdapter):
    async def emit(self, event):
        await my_system.send(event.to_dict())

set_adapter(MyAdapter())
```

## EventForwarder Utility

For integrating with existing server infrastructure:

```python
from amplifier_module_hooks_ui_bridge import EventForwarder, QueueAdapter

adapter = QueueAdapter()

# Transform events before sending (e.g., add conversationId)
def add_conversation_id(event_dict):
    event_dict["conversationId"] = current_conversation_id
    return event_dict

forwarder = EventForwarder(
    adapter, 
    sender=websocket.send_json,
    transform=add_conversation_id
)

# Run in background
task = asyncio.create_task(forwarder.run())

# Stop when done
forwarder.stop()
await task
```

## API Reference

### Main Exports

```python
from amplifier_module_hooks_ui_bridge import (
    # Schema
    UIEvent, UICommand, CommandTypes,
    
    # Event Types
    UIEventTypes,      # UI-friendly events
    NativeEventTypes,  # Native amplifier-core events
    EventTypes,        # Alias for UIEventTypes (backwards compat)
    
    # Adapters
    UIAdapter, QueueAdapter, TauriIPCAdapter, WebSocketAdapter, MockAdapter,
    
    # Bridge
    UIBridge,
    
    # Forwarder
    EventForwarder, BatchEventForwarder,
    
    # Functions
    get_bridge, set_adapter, get_adapter,
    create_queue_adapter,
    register_handler, register_enricher,
    emit_custom_event,
    mount,
)
```

## License

MIT
