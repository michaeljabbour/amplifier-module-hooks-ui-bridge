"""Session state management for UI bridge.

Tracks active child sessions — their depth in the delegation tree,
parent chain, agent name, and timing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SessionState:
    """State for a single session (root or nested agent)."""

    session_id: str
    parent_id: str | None = None
    depth: int = 0
    agent_name: str | None = None
    agent_type: str | None = None  # e.g., "foundation:explorer"
    agent_desc: str | None = None  # instruction snippet (truncated)
    start_time: float = field(default_factory=time.time)
    is_child: bool = False


class StateManager:
    """Manages state across multiple sessions (for nested agents)."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(
        self,
        session_id: str,
        parent_id: str | None = None,
    ) -> SessionState:
        """Get existing session or create new one.

        Computes depth from the parent chain. Parses agent_name from
        W3C session ID (takes the part after the last underscore).
        Sets is_child=True when parent_id is provided.
        """
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Compute depth from parent chain
        depth = 0
        if parent_id:
            parent = self._sessions.get(parent_id)
            depth = (parent.depth + 1) if parent else 1

        # Parse agent name from W3C session ID: "abc-def_foundation-explorer"
        agent_name: str | None = None
        if "_" in session_id:
            agent_name = session_id.rsplit("_", 1)[-1]

        state = SessionState(
            session_id=session_id,
            parent_id=parent_id,
            depth=depth,
            agent_name=agent_name,
            is_child=parent_id is not None,
        )
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> SessionState | None:
        """Remove and return session state."""
        return self._sessions.pop(session_id, None)

    def get_depth(self, session_id: str) -> int:
        """Return session depth, 0 if not found."""
        state = self._sessions.get(session_id)
        return state.depth if state else 0

    def get_breadcrumb(self, session_id: str) -> str:
        """Build 'main → Explorer → Deep-Scan' breadcrumb from parent chain."""
        parts: list[str] = []
        current = self._sessions.get(session_id)
        while current:
            name = current.agent_name or ("main" if current.depth == 0 else "sub-session")
            parts.append(name)
            current = self._sessions.get(current.parent_id) if current.parent_id else None
        parts.reverse()
        return " → ".join(parts)
