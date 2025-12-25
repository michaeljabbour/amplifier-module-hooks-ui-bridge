"""Base adapter protocol for UI transports.

Adapters handle the transport layer - how events get from the bridge
to the UI system and how commands come back.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from ..schema import UICommand, UIEvent


class UIAdapter(ABC):
    """Abstract base class for UI transport adapters.
    
    Implement this protocol to create custom adapters for any UI system.
    
    Built-in adapters:
        - QueueAdapter: asyncio.Queue for in-process (Textual)
        - TauriIPCAdapter: stdin/stdout for Tauri sidecar
        - WebSocketAdapter: WebSocket server for web clients
        - MockAdapter: In-memory for testing
    
    Example:
        class MyAdapter(UIAdapter):
            async def emit(self, event: UIEvent) -> None:
                await my_system.send(event.to_dict())
            
            async def receive(self) -> AsyncIterator[UICommand]:
                async for msg in my_system.listen():
                    yield UICommand.from_dict(msg)
    """
    
    @abstractmethod
    async def emit(self, event: UIEvent) -> None:
        """Send an event to the UI system.
        
        Args:
            event: The UIEvent to send
        """
        ...
    
    @abstractmethod
    async def receive(self) -> AsyncIterator[UICommand]:
        """Receive commands from the UI system.
        
        Yields:
            UICommand objects as they arrive from the UI
        """
        ...
        yield  # type: ignore  # Makes this a generator
    
    async def connect(self) -> None:
        """Initialize the adapter connection.
        
        Called when the module is mounted. Override to set up
        connections, start servers, etc.
        """
        pass
    
    async def disconnect(self) -> None:
        """Clean up the adapter connection.
        
        Called when the module is unmounted. Override to close
        connections, stop servers, etc.
        """
        pass
    
    async def emit_batch(self, events: list[UIEvent]) -> None:
        """Send multiple events at once.
        
        Default implementation calls emit() for each event.
        Override for more efficient batch sending.
        
        Args:
            events: List of UIEvents to send
        """
        for event in events:
            await self.emit(event)
