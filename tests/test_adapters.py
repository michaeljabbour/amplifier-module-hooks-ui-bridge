"""Tests for UI bridge adapters."""

import asyncio
from datetime import datetime

import pytest

from amplifier_module_hooks_ui_bridge import (
    MockAdapter,
    QueueAdapter,
    UICommand,
    UIEvent,
)


class TestQueueAdapter:
    """Tests for QueueAdapter."""
    
    @pytest.fixture
    def adapter(self):
        return QueueAdapter(name="test", maxsize=10)
    
    @pytest.mark.asyncio
    async def test_emit_event(self, adapter):
        """Test emitting an event to the queue."""
        await adapter.connect()
        
        event = UIEvent(
            type="test_event",
            timestamp=datetime.now(),
            data={"key": "value"},
        )
        
        await adapter.emit(event)
        
        # Event should be in the queue
        received = await adapter.event_queue.get()
        assert received.type == "test_event"
        assert received.data["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_send_command(self, adapter):
        """Test sending a command through the adapter."""
        await adapter.connect()
        
        command = UICommand(
            type="submit_prompt",
            data={"prompt": "Hello"},
        )
        
        await adapter.send_command(command)
        
        # Command should be in the queue
        received = await adapter.command_queue.get()
        assert received.type == "submit_prompt"
        assert received.data["prompt"] == "Hello"
    
    @pytest.mark.asyncio
    async def test_clear_events(self, adapter):
        """Test clearing the event queue."""
        await adapter.connect()
        
        # Add some events
        for i in range(5):
            await adapter.emit(UIEvent(
                type="test",
                timestamp=datetime.now(),
                data={"i": i},
            ))
        
        assert adapter.event_queue.qsize() == 5
        
        adapter.clear_events()
        
        assert adapter.event_queue.empty()
    
    @pytest.mark.asyncio
    async def test_queue_full_drops_event(self, adapter):
        """Test that full queue drops events gracefully."""
        await adapter.connect()
        
        # Fill the queue (maxsize=10)
        for i in range(10):
            await adapter.emit(UIEvent(
                type="test",
                timestamp=datetime.now(),
                data={"i": i},
            ))
        
        # This should not raise, just drop
        await adapter.emit(UIEvent(
            type="dropped",
            timestamp=datetime.now(),
            data={},
        ))
        
        # Queue should still have 10 items
        assert adapter.event_queue.qsize() == 10


class TestMockAdapter:
    """Tests for MockAdapter."""
    
    @pytest.fixture
    def adapter(self):
        return MockAdapter()
    
    @pytest.mark.asyncio
    async def test_captures_events(self, adapter):
        """Test that MockAdapter captures emitted events."""
        await adapter.connect()
        
        event1 = UIEvent(
            type="tool_start",
            timestamp=datetime.now(),
            data={"tool_name": "bash"},
        )
        event2 = UIEvent(
            type="tool_result",
            timestamp=datetime.now(),
            data={"tool_name": "bash", "success": True},
        )
        
        await adapter.emit(event1)
        await adapter.emit(event2)
        
        assert len(adapter.events) == 2
        assert adapter.events[0].type == "tool_start"
        assert adapter.events[1].type == "tool_result"
    
    @pytest.mark.asyncio
    async def test_get_events_by_type(self, adapter):
        """Test filtering events by type."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(type="tool_start", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="thinking_start", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="tool_result", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="tool_start", timestamp=datetime.now(), data={}))
        
        tool_starts = adapter.get_events_by_type("tool_start")
        
        assert len(tool_starts) == 2
    
    @pytest.mark.asyncio
    async def test_get_last_event(self, adapter):
        """Test getting the last event."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(type="first", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="second", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="last", timestamp=datetime.now(), data={}))
        
        last = adapter.get_last_event()
        
        assert last.type == "last"
    
    @pytest.mark.asyncio
    async def test_get_last_event_of_type(self, adapter):
        """Test getting the last event of a specific type."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(type="tool_start", timestamp=datetime.now(), data={"name": "first"}))
        await adapter.emit(UIEvent(type="other", timestamp=datetime.now(), data={}))
        await adapter.emit(UIEvent(type="tool_start", timestamp=datetime.now(), data={"name": "second"}))
        
        last_tool_start = adapter.get_last_event_of_type("tool_start")
        
        assert last_tool_start.data["name"] == "second"
    
    @pytest.mark.asyncio
    async def test_assert_event_emitted_success(self, adapter):
        """Test assert_event_emitted with matching event."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(
            type="tool_result",
            timestamp=datetime.now(),
            data={"tool_name": "bash", "success": True},
        ))
        
        # Should not raise
        event = adapter.assert_event_emitted("tool_result", tool_name="bash")
        assert event.data["success"] is True
    
    @pytest.mark.asyncio
    async def test_assert_event_emitted_failure(self, adapter):
        """Test assert_event_emitted raises when no match."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(
            type="tool_result",
            timestamp=datetime.now(),
            data={"tool_name": "bash"},
        ))
        
        with pytest.raises(AssertionError):
            adapter.assert_event_emitted("tool_result", tool_name="python")
    
    @pytest.mark.asyncio
    async def test_simulate_command(self, adapter):
        """Test simulating commands."""
        await adapter.connect()
        
        command = UICommand(
            type="submit_prompt",
            data={"prompt": "Test"},
        )
        
        await adapter.simulate_command(command)
        
        # Command should be in the command queue
        assert not adapter._command_queue.empty()
    
    @pytest.mark.asyncio
    async def test_clear(self, adapter):
        """Test clearing captured data."""
        await adapter.connect()
        
        await adapter.emit(UIEvent(type="test", timestamp=datetime.now(), data={}))
        
        assert len(adapter.events) == 1
        
        adapter.clear()
        
        assert len(adapter.events) == 0
    
    def test_get_last_event_empty(self, adapter):
        """Test get_last_event returns None when empty."""
        assert adapter.get_last_event() is None
    
    def test_get_last_event_of_type_not_found(self, adapter):
        """Test get_last_event_of_type returns None when not found."""
        assert adapter.get_last_event_of_type("nonexistent") is None
