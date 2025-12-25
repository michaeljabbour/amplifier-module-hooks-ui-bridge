"""Transport adapters for UI bridge.

Each adapter handles a different transport mechanism for
communicating UIEvents and UICommands between the bridge and UI.

Available adapters:
    - QueueAdapter: asyncio.Queue for in-process (Textual TUI)
    - TauriIPCAdapter: stdin/stdout JSON lines (Tauri desktop/mobile)
    - WebSocketAdapter: WebSocket server (Web dashboard)
    - MockAdapter: In-memory capture (Testing)
"""

from .base import UIAdapter
from .mock import MockAdapter
from .queue import QueueAdapter
from .tauri import TauriIPCAdapter
from .websocket import WebSocketAdapter

__all__ = [
    "UIAdapter",
    "QueueAdapter",
    "TauriIPCAdapter",
    "WebSocketAdapter",
    "MockAdapter",
]
