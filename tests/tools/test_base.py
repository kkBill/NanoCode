"""Tests for Tool base class and ToolRegistry."""

import pytest

from nanocode.tools import ToolRegistry, registry
from nanocode.tools.base import Tool


class DummyTool(Tool):
    """A concrete tool for testing."""

    def name(self) -> str:
        return "dummy"

    def description(self) -> str:
        return "A dummy tool for testing."

    def schema(self) -> dict:
        return {"type": "function", "function": {"name": self.name()}}

    def execute(self, **kwargs) -> str:
        return "ok"


def test_tool_is_abstract():
    """Tool cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Tool()


def test_dummy_tool_can_be_instantiated():
    tool = DummyTool()
    assert tool.name() == "dummy"
    assert tool.description() == "A dummy tool for testing."
    assert tool.schema()["type"] == "function"
    assert tool.execute() == "ok"


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get_tool("dummy") is tool
        assert reg.get_tool("nonexistent") is None

    def test_list_tools(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert reg.list_tools() == ["dummy"]

    def test_get_all_schemas(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        schemas = reg.get_all_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "dummy"

    def test_get_schemas_for_subagent_excludes_sub_agent(self):
        class SubAgentTool(DummyTool):
            def name(self):
                return "sub_agent"

        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(SubAgentTool())

        all_names = {s["function"]["name"] for s in reg.get_all_schemas()}
        subagent_names = {s["function"]["name"] for s in reg.get_schemas_for_subagent()}

        assert "sub_agent" in all_names
        assert "sub_agent" not in subagent_names
        assert "dummy" in subagent_names

    def test_list_tools_for_subagent(self):
        class SubAgentTool(DummyTool):
            def name(self):
                return "sub_agent"

        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(SubAgentTool())

        assert "sub_agent" not in reg.list_tools_for_subagent()
        assert "dummy" in reg.list_tools_for_subagent()


def test_global_registry_has_all_tools():
    expected = [
        "bash",
        "read_file",
        "write_file",
        "sub_agent",
        "load_skill",
        "create_task",
        "update_task",
        "get_task",
        "list_tasks",
        "run_background_task",
        "check_background_task",
        "save_memory",
        "list_memories",
        "create_cron",
        "delete_cron",
    ]
    for name in expected:
        assert registry.get_tool(name) is not None
    assert "sub_agent" in registry.list_tools()
