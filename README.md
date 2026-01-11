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

[hooks.config.transport]
type = "queue"  # For Textual TUI
```

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
| `QueueAdapter` | asyncio.Queue | Textual TUI |
| `TauriIPCAdapter` | stdin/stdout | Desktop/Mobile |
| `WebSocketAdapter` | WebSocket | Web Dashboard |
| `MockAdapter` | In-memory | Testing |

## Event Types

| Type | Description |
|------|-------------|
| `session_start` | Prompt submitted |
| `session_end` | Turn complete |
| `thinking_start` | Extended thinking begins |
| `thinking_end` | Extended thinking with content |
| `tool_start` | Tool invocation |
| `tool_result` | Tool completion |
| `token_usage` | Token counts |
| `error` | Errors |

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

[hooks.config.display]
show_thinking = false
truncate_output = 1000
```

### Level 2: Custom Handlers

```python
from amplifier_module_hooks_ui_bridge import register_handler

@register_handler("tool:post")
async def add_badge(event_name, data, bridge):
    data["badge"] = "⚡" if data.get("duration", 0) < 1 else ""
    return bridge.default_handler(event_name, data)
```

### Level 3: Custom Adapters

```python
from amplifier_module_hooks_ui_bridge import UIAdapter, set_adapter

class MyAdapter(UIAdapter):
    async def emit(self, event):
        await my_system.send(event.to_dict())

set_adapter(MyAdapter())
```

## License

MIT
