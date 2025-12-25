"""WebSocket adapter for web-based UIs.

This adapter runs a WebSocket server that broadcasts events to
all connected clients and receives commands from them.

Requires the 'websocket' extra:
    uv add amplifier-module-hooks-ui-bridge[websocket]
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, AsyncIterator

from .base import UIAdapter

if TYPE_CHECKING:
    from ..schema import UICommand, UIEvent

logger = logging.getLogger(__name__)


class WebSocketAdapter(UIAdapter):
    """Adapter using WebSocket for web clients.
    
    Runs a WebSocket server that:
    - Broadcasts UIEvents to all connected clients
    - Receives UICommands from any connected client
    
    Usage:
        # In profile.toml
        [hooks.config.transport]
        type = "websocket"
        host = "localhost"
        port = 8765
    
    Attributes:
        host: Server host
        port: Server port
        connections: Set of active WebSocket connections
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize the WebSocket adapter.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.connections: set = set()
        self._server = None
        self._command_queue: asyncio.Queue[UICommand] = asyncio.Queue()
        self._running = False
    
    async def connect(self) -> None:
        """Start the WebSocket server."""
        try:
            import websockets
        except ImportError:
            logger.error(
                "websockets package not installed. "
                "Install with: uv add amplifier-module-hooks-ui-bridge[websocket]"
            )
            return
        
        self._running = True
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    async def disconnect(self) -> None:
        """Stop the WebSocket server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")
    
    async def emit(self, event: UIEvent) -> None:
        """Broadcast event to all connected clients.
        
        Args:
            event: UIEvent to broadcast
        """
        if not self.connections:
            return
        
        message = event.to_json()
        
        # Send to all connections, ignore failures
        await asyncio.gather(
            *[self._send_safe(ws, message) for ws in self.connections],
            return_exceptions=True
        )
    
    async def _send_safe(self, websocket, message: str) -> None:
        """Send message to a websocket, handling errors."""
        try:
            await websocket.send(message)
        except Exception:
            # Connection may have closed
            self.connections.discard(websocket)
    
    async def receive(self) -> AsyncIterator[UICommand]:
        """Receive commands from connected clients.
        
        Yields:
            UICommand objects as they arrive
        """
        while self._running:
            try:
                command = await asyncio.wait_for(
                    self._command_queue.get(),
                    timeout=0.1
                )
                yield command
            except asyncio.TimeoutError:
                continue
    
    async def _handle_connection(self, websocket, path):
        """Handle a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            path: The request path
        """
        self.connections.add(websocket)
        logger.debug(f"Client connected. Total: {len(self.connections)}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    from ..schema import UICommand
                    command = UICommand.from_dict(data)
                    await self._command_queue.put(command)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from client")
                except Exception as e:
                    logger.warning(f"Error processing client message: {e}")
        except Exception:
            # Connection closed or error
            pass
        finally:
            self.connections.discard(websocket)
            logger.debug(f"Client disconnected. Total: {len(self.connections)}")
    
    async def emit_batch(self, events: list[UIEvent]) -> None:
        """Broadcast multiple events efficiently.
        
        Sends all events as a JSON array for batch processing.
        
        Args:
            events: List of UIEvents to broadcast
        """
        if not self.connections:
            return
        
        # Send as array for efficiency
        messages = [event.to_dict() for event in events]
        batch = json.dumps({"type": "batch", "events": messages})
        
        await asyncio.gather(
            *[self._send_safe(ws, batch) for ws in self.connections],
            return_exceptions=True
        )
