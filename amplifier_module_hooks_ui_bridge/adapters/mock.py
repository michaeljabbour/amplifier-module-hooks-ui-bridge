"""Mock adapter for testing.

This adapter captures events in memory and allows simulating
commands, making it easy to write tests for UI bridge functionality.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator

from .base import UIAdapter

if TYPE_CHECKING:
    from ..schema import UICommand, UIEvent


class MockAdapter(UIAdapter):
    """Mock adapter for testing - captures events, simulates commands.
    
    Usage:
        adapter = MockAdapter()
        await bridge.emit(some_event)
        
        # Check captured events
        assert len(adapter.events) == 1
        assert adapter.events[0].type == "tool_result"
        
        # Simulate commands
        await adapter.simulate_command(UICommand(
            type="submit_prompt",
            data={"prompt": "test"}
        ))
    
    Attributes:
        events: List of captured UIEvents
        commands: List of received UICommands (for inspection)
    """
    
    def __init__(self):
        """Initialize the mock adapter."""
        self.events: list[UIEvent] = []
        self.commands: list[UICommand] = []
        self._command_queue: asyncio.Queue[UICommand] = asyncio.Queue()
        self._connected = False
    
    async def connect(self) -> None:
        """Mark as connected."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Mark as disconnected."""
        self._connected = False
    
    async def emit(self, event: UIEvent) -> None:
        """Capture event in the events list.
        
        Args:
            event: UIEvent to capture
        """
        self.events.append(event)
    
    async def receive(self) -> AsyncIterator[UICommand]:
        """Receive simulated commands.
        
        Yields:
            UICommand objects that were simulated
        """
        while self._connected:
            try:
                command = await asyncio.wait_for(
                    self._command_queue.get(),
                    timeout=0.1
                )
                self.commands.append(command)
                yield command
            except asyncio.TimeoutError:
                continue
    
    async def simulate_command(self, command: UICommand) -> None:
        """Simulate a command from the UI.
        
        Use this in tests to simulate user actions.
        
        Args:
            command: UICommand to simulate
        """
        await self._command_queue.put(command)
    
    def clear(self) -> None:
        """Clear all captured events and commands."""
        self.events.clear()
        self.commands.clear()
    
    def get_events_by_type(self, event_type: str) -> list[UIEvent]:
        """Get all events of a specific type.
        
        Args:
            event_type: Event type to filter by
            
        Returns:
            List of matching events
        """
        return [e for e in self.events if e.type == event_type]
    
    def get_last_event(self) -> UIEvent | None:
        """Get the most recently captured event.
        
        Returns:
            Last UIEvent or None if no events
        """
        return self.events[-1] if self.events else None
    
    def get_last_event_of_type(self, event_type: str) -> UIEvent | None:
        """Get the most recent event of a specific type.
        
        Args:
            event_type: Event type to find
            
        Returns:
            Last matching UIEvent or None
        """
        for event in reversed(self.events):
            if event.type == event_type:
                return event
        return None
    
    def assert_event_emitted(self, event_type: str, **data_match) -> UIEvent:
        """Assert that an event of the given type was emitted.
        
        Args:
            event_type: Expected event type
            **data_match: Key-value pairs that must be in event.data
            
        Returns:
            The matching event
            
        Raises:
            AssertionError: If no matching event found
        """
        for event in self.events:
            if event.type != event_type:
                continue
            
            # Check data matches
            if all(event.data.get(k) == v for k, v in data_match.items()):
                return event
        
        raise AssertionError(
            f"No event of type '{event_type}' with data {data_match} found. "
            f"Events: {[e.type for e in self.events]}"
        )
