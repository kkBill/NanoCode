"""Tool registry and exports."""

from .background_tool import CheckBackgroundTask, RunBackgroundTask
from .base import Tool, ToolParams
from .bash_tool import Bash
from .cron_tool import CreateCron, DeleteCron
from .file_tool import ReadFile, WriteFile
from .memory_tool import ListMemories, SaveMemory
from .skill_tool import LoadSkill
from .subagent_tool import SubAgent
from .task_tool import CreateTask, GetTask, ListTasks, UpdateTask


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self):
        self.tools = {}

    def register(self, tool: Tool):
        """Register a tool in the registry."""
        self.tools[tool.name()] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self.tools.get(name, None)

    def get_all_schemas(self):
        """Get schemas for all tools."""
        return [tool.schema() for _, tool in self.tools.items()]

    def get_schemas_for_subagent(self):
        """Get schemas for sub-agent (excludes sub_agent to avoid infinite recursion)."""
        return [tool.schema() for name, tool in self.tools.items() if name != "sub_agent"]

    def list_tools(self):
        """List all tool names."""
        return list(self.tools.keys())

    def list_tools_for_subagent(self):
        """List tool names available to sub-agent."""
        return [name for name in self.tools.keys() if name != "sub_agent"]


# Global registry instance
registry = ToolRegistry()

# Register all tools
registry.register(Bash())
registry.register(ReadFile())
registry.register(WriteFile())
registry.register(SubAgent())
registry.register(LoadSkill())
registry.register(CreateTask())
registry.register(UpdateTask())
registry.register(GetTask())
registry.register(ListTasks())
registry.register(RunBackgroundTask())
registry.register(CheckBackgroundTask())
registry.register(SaveMemory())
registry.register(ListMemories())
registry.register(CreateCron())
registry.register(DeleteCron())


__all__ = [
    "Tool",
    "ToolParams",
    "ToolRegistry",
    "registry",
    "Bash",
    "ReadFile",
    "WriteFile",
    "SubAgent",
    "LoadSkill",
    "CreateTask",
    "UpdateTask",
    "GetTask",
    "ListTasks",
    "RunBackgroundTask",
    "CheckBackgroundTask",
    "SaveMemory",
    "ListMemories",
    "CreateCron",
    "DeleteCron",
]
