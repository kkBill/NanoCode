"""Skill loading system."""
import re
from pathlib import Path

import yaml

from ..config import SKILLS_DIR


class SkillLoader:
    """Load skills from SKILL.md files."""

    def __init__(self, skill_dir: Path = SKILLS_DIR):
        self.skill_dir = skill_dir

    def load_skill(self, name: str) -> str | None:
        """Load skill content by name."""
        skill_path = self.skill_dir / f"{name}/SKILL.md"
        if not skill_path.exists():
            return None
        return skill_path.read_text(encoding="utf-8")

    def load_instructions(self, name: str) -> str:
        """Load skill instructions (without frontmatter)."""
        content = self.load_skill(name)
        if not content:
            return f"Skill {name} not found."

        # Extract content after frontmatter
        pattern = r"^---\n(.*?)\n---\n?(.*)$"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

        if not match:
            return content.strip()

        instructions = match.group(2).strip()
        return instructions

    def load_metadata(self, name: str) -> dict:
        """Load skill metadata from frontmatter."""
        content = self.load_skill(name)
        if not content:
            return {}

        pattern = r"^---\n(.*?)\n---"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

        if not match:
            return {}

        metadata_text = match.group(1)
        metadata = yaml.safe_load(metadata_text)

        return metadata

    def list_skills(self) -> str:
        """List all available skills."""
        lines = ["<Available Skills>"]
        
        for item in self.skill_dir.iterdir():
            if not item.is_dir():
                continue
            skill_file = item / "SKILL.md"
            if not skill_file.exists():
                continue

            name = item.name
            metadata = self.load_metadata(name)
            description = metadata.get("description", "No description available.")
            # lines.append(f" - {name}: {description}")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{description}</description>")

        lines.append("</Available Skills>")
        return "\n".join(lines)
