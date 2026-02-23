"""Tests for SessionState and StateManager."""

import time

from amplifier_module_hooks_ui_bridge.state import SessionState, StateManager


class TestSessionState:
    """Verify SessionState dataclass defaults and creation."""

    def test_create_with_defaults(self):
        state = SessionState(session_id="abc-123")
        assert state.session_id == "abc-123"
        assert state.parent_id is None
        assert state.depth == 0
        assert state.agent_name is None
        assert state.agent_type is None
        assert state.agent_desc is None
        assert state.is_child is False
        assert isinstance(state.start_time, float)

    def test_create_with_all_fields(self):
        state = SessionState(
            session_id="child-1",
            parent_id="root-1",
            depth=2,
            agent_name="explorer",
            agent_type="foundation:explorer",
            agent_desc="Explore the codebase",
            is_child=True,
        )
        assert state.session_id == "child-1"
        assert state.parent_id == "root-1"
        assert state.depth == 2
        assert state.agent_name == "explorer"
        assert state.agent_type == "foundation:explorer"
        assert state.agent_desc == "Explore the codebase"
        assert state.is_child is True

    def test_start_time_auto_set(self):
        before = time.time()
        state = SessionState(session_id="t-1")
        after = time.time()
        assert before <= state.start_time <= after


class TestStateManagerGetOrCreate:
    """Verify get_or_create creates, retrieves, and computes depth."""

    def test_create_root_session(self):
        mgr = StateManager()
        state = mgr.get_or_create("root-1")
        assert state.session_id == "root-1"
        assert state.depth == 0
        assert state.is_child is False
        assert state.parent_id is None

    def test_returns_existing_session(self):
        mgr = StateManager()
        first = mgr.get_or_create("s-1")
        second = mgr.get_or_create("s-1")
        assert first is second

    def test_child_session_depth_1(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        child = mgr.get_or_create("child-1", parent_id="root")
        assert child.depth == 1
        assert child.is_child is True
        assert child.parent_id == "root"

    def test_grandchild_session_depth_2(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        mgr.get_or_create("child", parent_id="root")
        grandchild = mgr.get_or_create("grandchild", parent_id="child")
        assert grandchild.depth == 2
        assert grandchild.is_child is True

    def test_unknown_parent_defaults_depth_1(self):
        """If parent_id is given but not tracked, depth defaults to 1."""
        mgr = StateManager()
        child = mgr.get_or_create("orphan", parent_id="unknown-parent")
        assert child.depth == 1
        assert child.is_child is True


class TestAgentNameParsing:
    """Verify agent name is parsed from W3C-style session IDs."""

    def test_parses_agent_name_from_underscore(self):
        mgr = StateManager()
        state = mgr.get_or_create("abc-def_foundation-explorer", parent_id="root")
        assert state.agent_name == "foundation-explorer"

    def test_no_underscore_no_agent_name(self):
        mgr = StateManager()
        state = mgr.get_or_create("plain-session-id")
        assert state.agent_name is None

    def test_multiple_underscores_takes_last(self):
        mgr = StateManager()
        state = mgr.get_or_create("abc_def_bug-hunter", parent_id="root")
        assert state.agent_name == "bug-hunter"


class TestGetBreadcrumb:
    """Verify breadcrumb builds the parent chain string."""

    def test_root_only(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        assert mgr.get_breadcrumb("root") == "main"

    def test_one_child(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        child = mgr.get_or_create("child_explorer", parent_id="root")
        child.agent_name = "Explorer"
        assert mgr.get_breadcrumb("child_explorer") == "main → Explorer"

    def test_deep_chain(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        c1 = mgr.get_or_create("c1_explorer", parent_id="root")
        c1.agent_name = "Explorer"
        c2 = mgr.get_or_create("c2_deep-scan", parent_id="c1_explorer")
        c2.agent_name = "Deep-Scan"
        assert mgr.get_breadcrumb("c2_deep-scan") == "main → Explorer → Deep-Scan"

    def test_unknown_session_returns_empty(self):
        mgr = StateManager()
        assert mgr.get_breadcrumb("nonexistent") == ""


class TestStateManagerGet:
    """Verify get and get_depth lookups."""

    def test_get_existing(self):
        mgr = StateManager()
        created = mgr.get_or_create("s-1")
        assert mgr.get("s-1") is created

    def test_get_missing_returns_none(self):
        mgr = StateManager()
        assert mgr.get("nope") is None

    def test_get_depth_existing(self):
        mgr = StateManager()
        mgr.get_or_create("root")
        mgr.get_or_create("child", parent_id="root")
        assert mgr.get_depth("child") == 1

    def test_get_depth_missing_returns_zero(self):
        mgr = StateManager()
        assert mgr.get_depth("nope") == 0


class TestStateManagerRemove:
    """Verify remove returns state and cleans up."""

    def test_remove_returns_state(self):
        mgr = StateManager()
        mgr.get_or_create("s-1")
        removed = mgr.remove("s-1")
        assert removed is not None
        assert removed.session_id == "s-1"

    def test_remove_cleans_up(self):
        mgr = StateManager()
        mgr.get_or_create("s-1")
        mgr.remove("s-1")
        assert mgr.get("s-1") is None

    def test_remove_missing_returns_none(self):
        mgr = StateManager()
        assert mgr.remove("nope") is None
