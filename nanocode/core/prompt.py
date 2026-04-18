"""System prompt builder."""
import datetime
import os
from pathlib import Path

from ..utils import WORK_DIR
from ..tools.base import Tool


class SystemPromptBuilder:
    """
    Assemble system prompt from independent sections, including:
    1. core instructions: who you are, what you can do, etc.
    2. tool call: list all available tool descriptions.
    3. skills: list all available skill metadata.
    4. memory: load cross-session memories
    5. CLAUDE.md: layered instructions
    6. dynamic context: some runtime info and turn-specific info
    """

    def __init__(self) -> None:
        self.work_dir = WORK_DIR
        # Delay imports to avoid circular import
        # These are imported here because this class is instantiated in core/__init__.py
        # and importing at module level would cause circular import
        from . import memory_manager, skill_loader
        from ..tools import registry
        self.memory_manager = memory_manager
        self.skill_loader = skill_loader
        self.registry = registry

    def build(self) -> str:
        """Build the complete system prompt."""
        parts = []
        parts.append(self._build_core())
        parts.append(self._build_tool_list())
        parts.append(self._build_skill_list())
        parts.append(self._build_memory())
        parts.append(self._build_claude())

        parts.append("___Dynamic Boundary___")
        parts.append(self._build_dynamic_context())
        return "\n\n".join(parts)

    def _build_core(self) -> str:
        """Build core instructions."""
        return "# Role\nYou are a coding agent. Use available and appropriate tools to solve tasks."

    def _build_tool_list(self) -> str:
        """Build tool list section."""
        lines = ["# Tools\n<Available Tools>"]

        for tool_name in self.registry.list_tools():
            tool: Tool | None = self.registry.get_tool(tool_name)
            if tool:
                lines.append(f"    <name>{tool.name()}</name>")
                lines.append(f"    <description>{tool.description()}</description>")

        lines.append("</Available Tools>")
        return "\n".join(lines)

    def _build_skill_list(self) -> str:
        """Build skill list section."""
        lines = ["# Skills"]
        lines.append(self.skill_loader.list_skills())
        return "\n".join(lines)

    def _build_memory(self) -> str:
        """Build memory section."""
        return self.memory_manager.build_memory_prompt()

    def _build_claude(self) -> str:
        """Build CLAUDE.md section (placeholder)."""
        return ""

    def _build_dynamic_context(self) -> str:
        """Build dynamic context section."""
        lines = [
            "# Dynamic Context",
            f"- Current working directory: {self.work_dir}",
            f"- Current date: {datetime.date.today().isoformat()}",
            f"- Platform: {os.uname().sysname}",
        ]
        return "\n".join(lines)
