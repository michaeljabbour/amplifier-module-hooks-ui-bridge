"""Schema definitions for UI bridge events and commands.

This module defines the universal event/command schemas that work across
all UI transports (queue, IPC, WebSocket, stdio).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class UIEvent:
    """Universal event for any UI consumer.
    
    UIEvents are JSON-serializable and work across all transports:
    - asyncio.Queue (Textual TUI)
    - stdin/stdout JSON lines (Tauri sidecar)
    - WebSocket (Web dashboard)
    - stdio (VS Code extension)
    
    Attributes:
        type: Event type (e.g., "tool_result", "thinking_end")
        timestamp: When the event occurred
        data: Event-specific payload
        event_id: Unique identifier for this event
        parent_event_id: For correlating start/end pairs (e.g., tool_start → tool_result)
        session_id: Associated session ID
        agent_name: Sub-agent name (for delegated tasks)
        hints: Platform-specific hints (priority, ephemeral, silent)
    """
    
    type: str
    timestamp: datetime
    data: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    parent_event_id: str | None = None
    session_id: str | None = None
    agent_name: str | None = None
    hints: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        d: dict[str, Any] = {
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "event_id": self.event_id,
        }
        if self.parent_event_id:
            d["parent_event_id"] = self.parent_event_id
        if self.session_id:
            d["session_id"] = self.session_id
        if self.agent_name:
            d["agent_name"] = self.agent_name
        if self.hints:
            d["hints"] = self.hints
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UIEvent:
        """Create UIEvent from dictionary."""
        return cls(
            type=d["type"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            data=d.get("data", {}),
            event_id=d.get("event_id", str(uuid4())),
            parent_event_id=d.get("parent_event_id"),
            session_id=d.get("session_id"),
            agent_name=d.get("agent_name"),
            hints=d.get("hints"),
        )
    
    @classmethod
    def from_json(cls, s: str) -> UIEvent:
        """Create UIEvent from JSON string."""
        return cls.from_dict(json.loads(s))


@dataclass
class UICommand:
    """Command from UI to Amplifier.
    
    UICommands allow bidirectional communication - the UI can send
    commands back to Amplifier (submit prompt, cancel, switch session, etc.)
    
    Attributes:
        type: Command type (e.g., "submit_prompt", "cancel_generation")
        data: Command payload
        command_id: Unique ID for response correlation
    """
    
    type: str
    data: dict[str, Any]
    command_id: str = field(default_factory=lambda: str(uuid4()))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "data": self.data,
            "command_id": self.command_id,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UICommand:
        """Create UICommand from dictionary."""
        return cls(
            type=d["type"],
            data=d.get("data", {}),
            command_id=d.get("command_id", str(uuid4())),
        )
    
    @classmethod
    def from_json(cls, s: str) -> UICommand:
        """Create UICommand from JSON string."""
        return cls.from_dict(json.loads(s))


# Event type constants for type safety
class EventTypes:
    """Standard event type constants."""
    
    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_ERROR = "session_error"
    
    # Thinking/reasoning
    THINKING_START = "thinking_start"
    THINKING_CHUNK = "thinking_chunk"
    THINKING_END = "thinking_end"
    
    # Tool execution
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_RESULT = "tool_result"
    
    # Message streaming
    MESSAGE_START = "message_start"
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_END = "message_end"
    
    # Metadata
    TOKEN_USAGE = "token_usage"
    CONTEXT_UPDATE = "context_update"
    
    # Notifications
    NOTIFICATION = "notification"
    ERROR = "error"
    
    # Command responses
    COMMAND_RESULT = "command_result"
    COMMAND_ERROR = "command_error"


class CommandTypes:
    """Standard command type constants."""
    
    SUBMIT_PROMPT = "submit_prompt"
    CANCEL_GENERATION = "cancel_generation"
    SWITCH_SESSION = "switch_session"
    CREATE_SESSION = "create_session"
    DELETE_SESSION = "delete_session"
    LOAD_PROFILE = "load_profile"
    UPDATE_CONFIG = "update_config"
    CUSTOM = "custom"
