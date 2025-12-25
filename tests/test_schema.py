"""Tests for UIEvent and UICommand schema."""

import json
from datetime import datetime

import pytest

from amplifier_module_hooks_ui_bridge import UICommand, UIEvent


class TestUIEvent:
    """Tests for UIEvent dataclass."""
    
    def test_create_basic_event(self):
        """Test creating a basic event."""
        event = UIEvent(
            type="tool_result",
            timestamp=datetime(2024, 12, 25, 12, 0, 0),
            data={"tool_name": "bash", "success": True},
        )
        
        assert event.type == "tool_result"
        assert event.data["tool_name"] == "bash"
        assert event.event_id  # Should be auto-generated
    
    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = UIEvent(
            type="tool_start",
            timestamp=datetime(2024, 12, 25, 12, 0, 0),
            data={"tool_name": "bash"},
            event_id="test-id",
            session_id="session-123",
            agent_name="code-agent",
        )
        
        d = event.to_dict()
        
        assert d["type"] == "tool_start"
        assert d["timestamp"] == "2024-12-25T12:00:00"
        assert d["data"]["tool_name"] == "bash"
        assert d["event_id"] == "test-id"
        assert d["session_id"] == "session-123"
        assert d["agent_name"] == "code-agent"
    
    def test_event_to_json(self):
        """Test JSON serialization."""
        event = UIEvent(
            type="token_usage",
            timestamp=datetime(2024, 12, 25, 12, 0, 0),
            data={"input_tokens": 100, "output_tokens": 50},
            event_id="json-test",
        )
        
        json_str = event.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "token_usage"
        assert parsed["data"]["input_tokens"] == 100
    
    def test_event_from_dict(self):
        """Test creating event from dictionary."""
        d = {
            "type": "thinking_end",
            "timestamp": "2024-12-25T12:00:00",
            "data": {"content": "Let me think..."},
            "event_id": "from-dict-test",
            "parent_event_id": "parent-123",
        }
        
        event = UIEvent.from_dict(d)
        
        assert event.type == "thinking_end"
        assert event.data["content"] == "Let me think..."
        assert event.parent_event_id == "parent-123"
    
    def test_event_from_json(self):
        """Test creating event from JSON string."""
        json_str = '{"type": "session_start", "timestamp": "2024-12-25T12:00:00", "data": {"prompt": "Hello"}}'
        
        event = UIEvent.from_json(json_str)
        
        assert event.type == "session_start"
        assert event.data["prompt"] == "Hello"
    
    def test_optional_fields_not_in_dict(self):
        """Test that None optional fields are not included in dict."""
        event = UIEvent(
            type="test",
            timestamp=datetime.now(),
            data={},
        )
        
        d = event.to_dict()
        
        assert "parent_event_id" not in d
        assert "session_id" not in d
        assert "agent_name" not in d
        assert "hints" not in d
    
    def test_hints_included_when_set(self):
        """Test that hints are included when set."""
        event = UIEvent(
            type="notification",
            timestamp=datetime.now(),
            data={"message": "Test"},
            hints={"priority": "high", "ephemeral": True},
        )
        
        d = event.to_dict()
        
        assert d["hints"]["priority"] == "high"
        assert d["hints"]["ephemeral"] is True


class TestUICommand:
    """Tests for UICommand dataclass."""
    
    def test_create_basic_command(self):
        """Test creating a basic command."""
        command = UICommand(
            type="submit_prompt",
            data={"prompt": "Hello, Claude!"},
        )
        
        assert command.type == "submit_prompt"
        assert command.data["prompt"] == "Hello, Claude!"
        assert command.command_id  # Auto-generated
    
    def test_command_to_dict(self):
        """Test converting command to dictionary."""
        command = UICommand(
            type="switch_session",
            data={"session_id": "session-456"},
            command_id="cmd-123",
        )
        
        d = command.to_dict()
        
        assert d["type"] == "switch_session"
        assert d["data"]["session_id"] == "session-456"
        assert d["command_id"] == "cmd-123"
    
    def test_command_to_json(self):
        """Test JSON serialization."""
        command = UICommand(
            type="cancel_generation",
            data={},
            command_id="cancel-test",
        )
        
        json_str = command.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "cancel_generation"
        assert parsed["command_id"] == "cancel-test"
    
    def test_command_from_dict(self):
        """Test creating command from dictionary."""
        d = {
            "type": "load_profile",
            "data": {"profile": "coding"},
            "command_id": "from-dict-cmd",
        }
        
        command = UICommand.from_dict(d)
        
        assert command.type == "load_profile"
        assert command.data["profile"] == "coding"
        assert command.command_id == "from-dict-cmd"
    
    def test_command_from_json(self):
        """Test creating command from JSON string."""
        json_str = '{"type": "create_session", "data": {"profile": "default"}, "command_id": "json-cmd"}'
        
        command = UICommand.from_json(json_str)
        
        assert command.type == "create_session"
        assert command.data["profile"] == "default"


class TestRoundTrip:
    """Test round-trip serialization."""
    
    def test_event_roundtrip(self):
        """Test event survives JSON round-trip."""
        original = UIEvent(
            type="tool_result",
            timestamp=datetime(2024, 12, 25, 12, 30, 45),
            data={"tool_name": "bash", "success": True, "output": "file.txt"},
            event_id="roundtrip-test",
            parent_event_id="parent-event",
            session_id="session-xyz",
            agent_name="test-agent",
            hints={"priority": "normal"},
        )
        
        # Serialize and deserialize
        json_str = original.to_json()
        restored = UIEvent.from_json(json_str)
        
        assert restored.type == original.type
        assert restored.data == original.data
        assert restored.event_id == original.event_id
        assert restored.parent_event_id == original.parent_event_id
        assert restored.session_id == original.session_id
        assert restored.agent_name == original.agent_name
        assert restored.hints == original.hints
    
    def test_command_roundtrip(self):
        """Test command survives JSON round-trip."""
        original = UICommand(
            type="submit_prompt",
            data={"prompt": "Test prompt", "options": {"stream": True}},
            command_id="roundtrip-cmd",
        )
        
        json_str = original.to_json()
        restored = UICommand.from_json(json_str)
        
        assert restored.type == original.type
        assert restored.data == original.data
        assert restored.command_id == original.command_id
