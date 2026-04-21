"""Memory management tools."""

import logging

from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class SaveMemory(Tool):
    """Save a memory item."""

    PARAMS = (
        ToolParams()
        .param("name", str, description="Unique name for the memory (letters, numbers, hyphens, underscores only)")
        .param("type", str, enum=["user", "feedback", "project", "reference"], description="Type of memory")
        .param("description", str, description="Brief description of what this memory contains")
        .param("content", str, description="The actual memory content to save")
        .required("name", "type", "description", "content")
    )

    def name(self) -> str:
        return "save_memory"

    def description(self) -> str:
        return "Save a memory item for future reference. Use for user preferences, repeated feedback, project facts, or external references."

    def execute(self, **kwargs) -> str:
        from ..core import memory_manager

        name = kwargs.get("name", "")
        mem_type = kwargs.get("type", "")
        description = kwargs.get("description", "")
        content = kwargs.get("content", "")
        logger.info("save_memory(name=%s, type=%s)", name, mem_type)

        if not name or not mem_type or not description:
            return "Error: name, type, and description are required."

        success = memory_manager.save_memory(name, mem_type, description, content)
        if success:
            return f"Memory '{name}' saved successfully. Type: {mem_type}"
        return f"Failed to save memory '{name}'. Check the error message above."


class ListMemories(Tool):
    """List all saved memories."""

    # No parameters

    def name(self) -> str:
        return "list_memories"

    def description(self) -> str:
        return "List all saved memories with their names, types, and descriptions."

    def execute(self, **kwargs) -> str:
        from ..core import memory_manager

        logger.info("list_memories()")
        return memory_manager.list_memories()
