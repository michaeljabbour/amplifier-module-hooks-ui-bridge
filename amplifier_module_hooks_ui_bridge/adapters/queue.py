"""Queue adapter for in-process UI (Textual TUI).

This adapter uses asyncio.Queue for communication between the
UI bridge and a Textual application running in the same process.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator

from .base import UIAdapter

if TYPE_CHECKING:
    from ..schema import UICommand, UIEvent


class QueueAdapter(UIAdapter):
    """Adapter using asyncio.Queue for in-process communication.
    
    This is the primary adapter for Textual TUI applications where
    the UI runs in the same Python process as Amplifier.
    
    Usage:
        # In your Textual app
        from amplifier_module_hooks_ui_bridge import create_queue_adapter
        
        adapter = create_queue_adapter()
        
        # Consume events
        async def event_consumer():
            while True:
                event = await adapter.event_queue.get()
                handle_event(event)
        
        # Send commands
        await adapter.send_command(UICommand(
            type="submit_prompt",
            data={"prompt": "Hello!"}
        ))
    
    Attributes:
        event_queue: Queue where UIEvents are pushed (UI reads from here)
        command_queue: Queue where UICommands are pushed (bridge reads from here)
        name: Optional name for the adapter instance
    """
    
    def __init__(self, name: str = "default", maxsize: int = 1000):
        """Initialize the queue adapter.
        
        Args:
            name: Name for this adapter instance
            maxsize: Maximum queue size (0 = unlimited)
        """
        self.name = name
        self.event_queue: asyncio.Queue[UIEvent] = asyncio.Queue(maxsize=maxsize)
        self.command_queue: asyncio.Queue[UICommand] = asyncio.Queue()
        self._connected = False
    
    async def connect(self) -> None:
        """Mark adapter as connected."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Mark adapter as disconnected."""
        self._connected = False
    
    async def emit(self, event: UIEvent) -> None:
        """Push event to the event queue.
        
        If the queue is full, drops the event and logs a warning.
        
        Args:
            event: UIEvent to push
        """
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Log would go here, but we don't have logging set up
            # In production, you might want to handle this differently
            pass
    
    async def receive(self) -> AsyncIterator[UICommand]:
        """Receive commands from the command queue.
        
        Yields:
            UICommand objects as they arrive
        """
        while self._connected:
            try:
                command = await asyncio.wait_for(
                    self.command_queue.get(),
                    timeout=0.1
                )
                yield command
            except asyncio.TimeoutError:
                continue
    
    async def send_command(self, command: UICommand) -> None:
        """Send a command to the bridge (called by UI).
        
        This is how the Textual app sends commands to Amplifier.
        
        Args:
            command: UICommand to send
        """
        await self.command_queue.put(command)
    
    def clear_events(self) -> None:
        """Clear all pending events from the queue."""
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    def clear_commands(self) -> None:
        """Clear all pending commands from the queue."""
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
