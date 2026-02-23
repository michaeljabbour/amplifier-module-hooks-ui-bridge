"""Tests for UIEventTypes agent event constants."""

from amplifier_module_hooks_ui_bridge.events import UIEventTypes


class TestAgentEventTypes:
    """Verify agent/delegation event type constants exist with correct values."""

    def test_agent_start(self):
        assert UIEventTypes.AGENT_START == "agent_start"

    def test_agent_delta(self):
        assert UIEventTypes.AGENT_DELTA == "agent_delta"

    def test_agent_thinking(self):
        assert UIEventTypes.AGENT_THINKING == "agent_thinking"

    def test_agent_tool(self):
        assert UIEventTypes.AGENT_TOOL == "agent_tool"

    def test_agent_complete(self):
        assert UIEventTypes.AGENT_COMPLETE == "agent_complete"

    def test_agent_constants_use_snake_case_values(self):
        """All agent constants use snake_case string values (no colons)."""
        agent_names = (
            "AGENT_START",
            "AGENT_DELTA",
            "AGENT_THINKING",
            "AGENT_TOOL",
            "AGENT_COMPLETE",
        )
        for name in agent_names:
            value = getattr(UIEventTypes, name)
            assert ":" not in value, f"{name} should use snake_case, got {value!r}"
