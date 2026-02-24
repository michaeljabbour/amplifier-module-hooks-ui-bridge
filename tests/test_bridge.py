"""Tests for UIBridge."""

from datetime import datetime

import pytest

from amplifier_module_hooks_ui_bridge import MockAdapter, UIBridge, UICommand, UIEvent


class TestUIBridge:
    """Tests for UIBridge class."""
    
    @pytest.fixture
    def bridge(self):
        """Create a bridge with mock adapter."""
        adapter = MockAdapter()
        bridge = UIBridge()
        bridge.set_adapter(adapter)
        return bridge, adapter
    
    @pytest.mark.asyncio
    async def test_handle_tool_pre(self, bridge):
        """Test handling tool:pre event."""
        bridge, adapter = bridge
        await adapter.connect()
        
        await bridge.handle_event("tool:pre", {
            "tool_name": "bash",
            "tool_input": {"command": "ls"},
        })
        
        assert len(adapter.events) == 1
        event = adapter.events[0]
        assert event.type == "tool_start"
        assert event.data["tool_name"] == "bash"
    
    @pytest.mark.asyncio
    async def test_handle_tool_post(self, bridge):
        """Test handling tool:post event."""
        bridge, adapter = bridge
        await adapter.connect()
        
        # First emit tool:pre to set up correlation
        await bridge.handle_event("tool:pre", {
            "tool_name": "bash",
            "tool_input": {},
        })
        
        # Then tool:post
        await bridge.handle_event("tool:post", {
            "tool_name": "bash",
            "tool_response": {"success": True, "output": "file.txt"},
        })
        
        assert len(adapter.events) == 2
        result_event = adapter.events[1]
        assert result_event.type == "tool_result"
        assert result_event.data["success"] is True
        assert "duration_ms" in result_event.data
    
    @pytest.mark.asyncio
    async def test_handle_thinking_events(self, bridge):
        """Test handling thinking block events."""
        bridge, adapter = bridge
        await adapter.connect()
        
        # thinking start
        await bridge.handle_event("content_block:start", {
            "block_type": "thinking",
            "block_index": 0,
        })
        
        assert len(adapter.events) == 1
        assert adapter.events[0].type == "thinking_start"
        
        # thinking end
        await bridge.handle_event("content_block:end", {
            "block_index": 0,
            "block": {"type": "thinking", "thinking": "Let me analyze..."},
        })
        
        # Should have thinking_end (and possibly token_usage)
        thinking_ends = adapter.get_events_by_type("thinking_end")
        assert len(thinking_ends) == 1
        assert thinking_ends[0].data["content"] == "Let me analyze..."
    
    @pytest.mark.asyncio
    async def test_event_filtering_by_pattern(self, bridge):
        """Test that events are filtered by configured patterns."""
        adapter = MockAdapter()
        bridge = UIBridge(config={"events": ["tool:*"]})  # Only tool events
        bridge.set_adapter(adapter)
        await adapter.connect()
        
        # Tool event should pass
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        assert len(adapter.events) == 1
        
        # Session event should be filtered
        await bridge.handle_event("session:start", {"prompt": "Hello"})
        assert len(adapter.events) == 1  # Still 1
    
    @pytest.mark.asyncio
    async def test_custom_handler(self, bridge):
        """Test registering a custom handler."""
        bridge, adapter = bridge
        await adapter.connect()
        
        @bridge.on("tool:post")
        async def add_badge(event_name, data, b):
            data["badge"] = "⚡"
            return b.default_handler(event_name, data)
        
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        await bridge.handle_event("tool:post", {
            "tool_name": "bash",
            "tool_response": {"success": True},
        })
        
        result = adapter.get_last_event_of_type("tool_result")
        assert result.data["badge"] == "⚡"
    
    @pytest.mark.asyncio
    async def test_filter_pipeline(self, bridge):
        """Test adding a filter to drop events."""
        bridge, adapter = bridge
        await adapter.connect()
        
        @bridge.filter
        def drop_thinking(event):
            return event.type != "thinking_start"
        
        await bridge.handle_event("content_block:start", {
            "block_type": "thinking",
            "block_index": 0,
        })
        
        # Thinking start should be filtered out
        assert len(adapter.events) == 0
    
    @pytest.mark.asyncio
    async def test_transform_pipeline(self, bridge):
        """Test adding a transformer."""
        bridge, adapter = bridge
        await adapter.connect()
        
        @bridge.transform
        def add_version(event):
            event.data["version"] = "1.0.0"
            return event
        
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        
        event = adapter.get_last_event()
        assert event.data["version"] == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_truncate_output(self):
        """Test output truncation."""
        adapter = MockAdapter()
        bridge = UIBridge(config={
            "display": {"truncate_output": 20, "show_tool_output": True}
        })
        bridge.set_adapter(adapter)
        await adapter.connect()
        
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        await bridge.handle_event("tool:post", {
            "tool_name": "bash",
            "tool_response": {"output": "x" * 100},
        })
        
        result = adapter.get_last_event_of_type("tool_result")
        assert len(result.data["output"]) < 100
        assert "more chars" in result.data["output"]
    
    @pytest.mark.asyncio
    async def test_agent_name_parsing(self, bridge):
        """Test agent name is parsed from session_id."""
        bridge, adapter = bridge
        await adapter.connect()
        
        await bridge.handle_event("tool:pre", {
            "tool_name": "bash",
            "session_id": "parent-session_code-reviewer",
        })
        
        event = adapter.get_last_event()
        assert event.agent_name == "code-reviewer"
    
    @pytest.mark.asyncio
    async def test_event_correlation(self, bridge):
        """Test that tool_result has parent_event_id from tool_start."""
        bridge, adapter = bridge
        await adapter.connect()
        
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        start_event = adapter.get_last_event()
        
        await bridge.handle_event("tool:post", {
            "tool_name": "bash",
            "tool_response": {"success": True},
        })
        result_event = adapter.get_last_event()
        
        assert result_event.parent_event_id == start_event.event_id
    
    @pytest.mark.asyncio
    async def test_command_handling(self, bridge):
        """Test registering and handling commands."""
        bridge, adapter = bridge
        
        results = []
        
        @bridge.on_command("submit_prompt")
        async def handle_prompt(data):
            results.append(data["prompt"])
            return {"status": "ok"}
        
        command = UICommand(
            type="submit_prompt",
            data={"prompt": "Hello, Claude!"},
        )
        
        result = await bridge.handle_command(command)
        
        assert results == ["Hello, Claude!"]
        assert result["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_unknown_command_raises(self, bridge):
        """Test that unknown command type raises error."""
        bridge, adapter = bridge
        
        command = UICommand(
            type="unknown_command",
            data={},
        )
        
        with pytest.raises(ValueError, match="Unknown command type"):
            await bridge.handle_command(command)
    
    @pytest.mark.asyncio
    async def test_event_history(self):
        """Test event history when enabled."""
        adapter = MockAdapter()
        bridge = UIBridge(config={
            "history": {"enabled": True, "max_events": 5}
        })
        bridge.set_adapter(adapter)
        await adapter.connect()
        
        # Emit more than max_events
        for i in range(10):
            await bridge.handle_event("tool:pre", {"tool_name": f"tool-{i}"})
        
        history = bridge.event_history
        
        # Should only keep last 5
        assert len(history) == 5
        assert history[-1].data["tool_name"] == "tool-9"
    
    @pytest.mark.asyncio
    async def test_preset_minimal(self):
        """Test minimal preset filters events."""
        adapter = MockAdapter()
        bridge = UIBridge(config={"preset": "minimal"})
        bridge.set_adapter(adapter)
        await adapter.connect()
        
        # tool:pre should not pass (only tool:post in minimal)
        await bridge.handle_event("tool:pre", {"tool_name": "bash"})
        assert len(adapter.events) == 0
        
        # tool:post should pass
        await bridge.handle_event("tool:post", {
            "tool_name": "bash",
            "tool_response": {"success": True},
        })
        assert len(adapter.events) == 1


class TestUIBridgeConfiguration:
    """Tests for bridge configuration options."""
    
    def test_default_config(self):
        """Test bridge uses default config."""
        bridge = UIBridge()
        
        assert bridge.config["display"]["show_thinking"] is True
        assert bridge.config["display"]["truncate_output"] == 500
    
    def test_custom_config_merged(self):
        """Test custom config is merged with defaults."""
        bridge = UIBridge(config={
            "display": {"show_thinking": False}
        })
        
        assert bridge.config["display"]["show_thinking"] is False
        assert bridge.config["display"]["truncate_output"] == 500  # From defaults
    
    def test_preset_overrides_events(self):
        """Test preset overrides events list."""
        bridge = UIBridge(config={"preset": "verbose"})
        
        assert bridge.config["events"] == ["*"]


# Standard hook events that register_on_coordinator should register
STANDARD_HOOK_EVENTS = {
    "content_block:start",
    "content_block:delta",
    "content_block:end",
    "thinking:delta",
    "thinking:final",
    "tool:pre",
    "tool:post",
    "session:start",
    "session:end",
    "orchestrator:complete",
}


class TestRegisterOnCoordinator:
    """Tests for UIBridge.register_on_coordinator()."""

    @pytest.fixture
    def mock_coordinator(self):
        """Mock coordinator with hooks that track registrations."""

        class MockHooks:
            def __init__(self):
                self.registered: dict[str, list] = {}

            def register(self, event, handler, priority=None, name=None):
                self.registered.setdefault(event, []).append(handler)

                def unregister():
                    if event in self.registered:
                        self.registered[event] = [
                            h for h in self.registered[event] if h is not handler
                        ]

                return unregister

        class MockCoordinator:
            def __init__(self):
                self.hooks = MockHooks()

        return MockCoordinator()

    @pytest.fixture
    def bridge_with_adapter(self):
        """Create a UIBridge with connected mock adapter."""
        adapter = MockAdapter()
        bridge = UIBridge()
        bridge.set_adapter(adapter)
        return bridge, adapter

    def test_non_child_registers_all_standard_events(
        self, bridge_with_adapter, mock_coordinator
    ):
        """is_child=False registers handlers for all 10 standard hook events."""
        bridge, _ = bridge_with_adapter
        bridge.register_on_coordinator(mock_coordinator)
        assert set(mock_coordinator.hooks.registered.keys()) == STANDARD_HOOK_EVENTS

    def test_child_registers_events_and_creates_session_state(
        self, bridge_with_adapter, mock_coordinator
    ):
        """is_child=True registers handlers AND creates SessionState."""
        bridge, _ = bridge_with_adapter

        bridge.register_on_coordinator(
            mock_coordinator,
            is_child=True,
            session_id="parent-abc_explorer",
            agent_name="explorer",
        )

        # All standard events registered
        assert set(mock_coordinator.hooks.registered.keys()) == STANDARD_HOOK_EVENTS

        # SessionState created with correct fields
        state = bridge._state_manager.get("parent-abc_explorer")
        assert state is not None
        assert state.session_id == "parent-abc_explorer"
        assert state.agent_name == "explorer"

    def test_unregister_callables_remove_handlers(
        self, bridge_with_adapter, mock_coordinator
    ):
        """Returned callables actually unregister all handlers."""
        bridge, _ = bridge_with_adapter

        unregisters = bridge.register_on_coordinator(mock_coordinator)
        assert len(unregisters) == len(STANDARD_HOOK_EVENTS)
        assert all(callable(u) for u in unregisters)

        # Unregister everything
        for unreg in unregisters:
            unreg()

        # All handler lists should be empty
        for event, handlers in mock_coordinator.hooks.registered.items():
            assert handlers == [], f"Handler still registered for {event}"

    @pytest.mark.asyncio
    async def test_child_handler_injects_metadata(
        self, bridge_with_adapter, mock_coordinator
    ):
        """Child handler injects _child_session_id and _child_agent_name into event data."""
        bridge, adapter = bridge_with_adapter
        await adapter.connect()

        bridge.register_on_coordinator(
            mock_coordinator,
            is_child=True,
            session_id="child-sess-123",
            agent_name="bug-hunter",
        )

        # tool:pre sets up correlation state in the bridge
        pre_handler = mock_coordinator.hooks.registered["tool:pre"][0]
        await pre_handler("tool:pre", {"tool_name": "bash", "tool_input": {}})

        # tool:post in ui_friendly mode preserves custom fields from data
        post_handler = mock_coordinator.hooks.registered["tool:post"][0]
        await post_handler(
            "tool:post",
            {"tool_name": "bash", "tool_response": {"success": True, "output": "ok"}},
        )

        result_event = adapter.get_last_event_of_type("tool_result")
        assert result_event is not None
        assert result_event.data["_child_session_id"] == "child-sess-123"
        assert result_event.data["_child_agent_name"] == "bug-hunter"
