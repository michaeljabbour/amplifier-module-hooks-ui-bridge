"""Event type constants for UI bridge.

This module provides two sets of event type constants:
- NativeEventTypes: Direct pass-through of amplifier-core event names
- UIEventTypes: Semantic UI-friendly event names (legacy/simple UIs)

Use the bridge's `event_mode` config to choose which set is emitted:
- "native": Emits NativeEventTypes (recommended for sophisticated UIs)
- "ui_friendly": Emits UIEventTypes (simpler, more abstract)
- "both": Emits both types (for migration/debugging)
"""


class NativeEventTypes:
    """Native amplifier-core event types (pass-through mode).
    
    These match the canonical event names from amplifier-core.
    Use with `event_mode: "native"` for maximum fidelity.
    
    Recommended for sophisticated UIs like amplifier-desktop that
    need fine-grained control over streaming and tool execution.
    """
    
    # Session lifecycle
    SESSION_START = "session:start"
    SESSION_END = "session:end"
    
    # Content streaming (real-time text/thinking)
    CONTENT_BLOCK_START = "content_block:start"
    CONTENT_BLOCK_DELTA = "content_block:delta"
    CONTENT_BLOCK_END = "content_block:end"
    
    # Thinking/reasoning streaming
    THINKING_DELTA = "thinking:delta"
    
    # Tool execution
    TOOL_PRE = "tool:pre"
    TOOL_POST = "tool:post"
    
    # Orchestrator lifecycle
    ORCHESTRATOR_COMPLETE = "orchestrator:complete"
    
    # Provider events
    PROVIDER_START = "provider:start"
    PROVIDER_END = "provider:end"
    
    # Approval workflow
    APPROVAL_REQUESTED = "approval:requested"
    APPROVAL_RESOLVED = "approval:resolved"
    
    # Errors
    ERROR = "error"


class UIEventTypes:
    """UI-friendly semantic event types.
    
    These are higher-level abstractions over amplifier-core events.
    Use with `event_mode: "ui_friendly"` for simpler UIs.
    
    Good for Textual TUIs or simple web UIs that don't need
    fine-grained streaming control.
    """
    
    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_ERROR = "session_error"
    
    # Thinking/reasoning (collapsed from content_block:* events)
    THINKING_START = "thinking_start"
    THINKING_CHUNK = "thinking_chunk"
    THINKING_END = "thinking_end"
    
    # Tool execution (mapped from tool:pre/post)
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_RESULT = "tool_result"
    
    # Message streaming (collapsed from content_block:* text events)
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


# Backwards compatibility: EventTypes is alias for UIEventTypes
# This maintains compatibility with existing code using EventTypes
EventTypes = UIEventTypes
