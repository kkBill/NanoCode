"""Memory management system."""

import logging
import re

import yaml

from ..utils import WORK_DIR

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manage persistent memories with YAML frontmatter markdown files."""

    def __init__(self):
        self.dir = WORK_DIR / ".memory"
        self.dir.mkdir(exist_ok=True)
        self.types = ["user", "feedback", "project", "reference"]
        self.index_file = self.dir / "MEMORY.md"
        # Store memory items in-memory: name -> {type, description, content}
        self.memories: dict[str, dict] = {}

    def load(self):
        """Load all memory items from disk to in-memory."""
        memory_files = list(self.dir.glob("*.md"))

        for file in memory_files:
            if file.name == "MEMORY.md":
                continue
            try:
                content = file.read_text(encoding="utf-8")
                metadata = self._parse_frontmatter(content)
                if metadata:
                    name = metadata.get("name", file.stem)
                    self.memories[name] = {
                        "type": metadata.get("type", "project"),
                        "description": metadata.get("description", ""),
                        "content": self._extract_body(content),
                    }
            except Exception as e:
                logger.exception("Error loading memory file %s: %s", file, e)

    def _parse_frontmatter(self, content: str) -> dict | None:
        """Parse YAML frontmatter from markdown file."""
        pattern = r"^---\n(.*?)\n---"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        if not match:
            return None
        try:
            return yaml.safe_load(match.group(1))
        except Exception:
            return None

    def _extract_body(self, content: str) -> str:
        """Extract the body content after frontmatter."""
        pattern = r"^---\n.*?\n---\n?(.*)$"
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
        return content.strip()

    def build_memory_prompt(self) -> str:
        """Build memory context for injection into the system prompt."""
        if not self.memories:
            return ""

        parts = ["# Memories\nYou have access to the following persistent memories:"]

        # Group memories by type
        for mem_type in self.types:
            type_memories = [(name, data) for name, data in self.memories.items() if data["type"] == mem_type]
            if not type_memories:
                continue

            parts.append(f"## {mem_type}")
            for name, data in type_memories:
                parts.append(f"- {name}: {data['description']}")
                if data["content"]:
                    parts.append(f" {data['content']}")
            parts.append("")

        return "\n".join(parts)

    def save_memory(self, name: str, mem_type: str, description: str, content: str) -> bool:
        """Save memory to a new markdown file."""
        # Validate type
        if mem_type not in self.types:
            logger.warning("Invalid memory type: %s. Must be one of %s", mem_type, self.types)
            return False

        # Validate name (avoid special characters)
        if not name or not re.match(r"^[\w\-]+$", name):
            logger.warning("Invalid memory name: %s. Use only letters, numbers, hyphens, and underscores.", name)
            return False

        # Check for duplicate
        if name in self.memories:
            logger.warning(
                "Memory with name '%s' already exists. Use a different name or update existing memory.", name
            )
            return False

        # Create markdown file with frontmatter
        file_content = f"""---
name: {name}
type: {mem_type}
description: {description}
---
{content}
"""
        file_path = self.dir / f"memory_{name}.md"
        try:
            file_path.write_text(file_content, encoding="utf-8")
            # Update in-memory cache
            self.memories[name] = {
                "type": mem_type,
                "description": description,
                "content": content,
            }
            logger.info("Memory '%s' saved successfully.", name)
            return True
        except Exception as e:
            logger.exception("Error saving memory '%s': %s", name, e)
            return False

    def list_memories(self) -> str:
        """List all memories with their metadata."""
        if not self.memories:
            return "No memories saved yet."

        lines = []
        for name, data in self.memories.items():
            lines.append(f"- {name} [{data['type']}]: {data['description']}")
        return "\n".join(lines)
