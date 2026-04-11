"""Memory management tools."""
from ..core import memory_manager
from .base import Tool


class SaveMemory(Tool):
    """Save a memory item."""

    def name(self) -> str:
        return "save_memory"

    def description(self) -> str:
        return "Save a memory item for future reference. Use for user preferences, repeated feedback, project facts, or external references."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique name for the memory (letters, numbers, hyphens, underscores only)",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["user", "feedback", "project", "reference"],
                            "description": "Type of memory: user (preferences), feedback (repeated feedback), project (non-obvious facts), reference (external resources)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of what this memory contains",
                        },
                        "content": {
                            "type": "string",
                            "description": "The actual memory content to save",
                        },
                    },
                    "required": ["name", "type", "description", "content"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        name = kwargs.get("name", "")
        mem_type = kwargs.get("type", "")
        description = kwargs.get("description", "")
        content = kwargs.get("content", "")
        print(f"save_memory(name={name}, type={mem_type})")

        if not name or not mem_type or not description:
            return "Error: name, type, and description are required."

        success = memory_manager.save_memory(name, mem_type, description, content)
        if success:
            return f"Memory '{name}' saved successfully. Type: {mem_type}"
        return f"Failed to save memory '{name}'. Check the error message above."


class ListMemories(Tool):
    """List all saved memories."""

    def name(self) -> str:
        return "list_memories"

    def description(self) -> str:
        return "List all saved memories with their names, types, and descriptions."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    def execute(self, **kwargs) -> str:
        print("list_memories()")
        return memory_manager.list_memories()
