"""Skill loading tool."""

import logging

from .base import Tool

logger = logging.getLogger(__name__)


class LoadSkill(Tool):
    """Load skill instructions by name."""

    def name(self) -> str:
        return "load_skill"

    def description(self) -> str:
        return "Load instructions for a skill by name. Use it when you need to use a skill but don't know how."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                    },
                    "required": ["skill_name"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        from ..core import skill_loader

        skill_name = kwargs.get("skill_name", "")
        logger.info("load_skill(name=%s)", skill_name)

        if not skill_name:
            return "No skill name provided."

        instructions = skill_loader.load_instructions(skill_name)
        return instructions
