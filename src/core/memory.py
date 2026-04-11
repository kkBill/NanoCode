"""Memory management system."""
import re
from pathlib import Path

import yaml

from ..config import WORKDIR


class MemoryManager:
    """Manage persistent memories with YAML frontmatter markdown files."""

    def __init__(self, memory_dir: Path = None):
        if memory_dir is None:
            memory_dir = WORKDIR / ".memory"
        self.dir = memory_dir
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
                print(f"Error loading memory file {file}: {e}")

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

        parts = ["## Memories:", ""]

        # Group memories by type
        for mem_type in self.types:
            type_memories = [
                (name, data) for name, data in self.memories.items() if data["type"] == mem_type
            ]
            if not type_memories:
                continue

            parts.append(f"### {mem_type}")
            for name, data in type_memories:
                parts.append(f"- **{name}**: {data['description']}")
                if data["content"]:
                    parts.append(f"  {data['content']}")
            parts.append("")

        return "\n".join(parts)

    def save_memory(self, name: str, mem_type: str, description: str, content: str) -> bool:
        """Save memory to a new markdown file."""
        # Validate type
        if mem_type not in self.types:
            print(f"Invalid memory type: {mem_type}. Must be one of {self.types}")
            return False

        # Validate name (avoid special characters)
        if not name or not re.match(r"^[\w\-]+$", name):
            print(f"Invalid memory name: {name}. Use only letters, numbers, hyphens, and underscores.")
            return False

        # Check for duplicate
        if name in self.memories:
            print(f"Memory with name '{name}' already exists. Use a different name or update existing memory.")
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
            print(f"Memory '{name}' saved successfully.")
            return True
        except Exception as e:
            print(f"Error saving memory '{name}': {e}")
            return False

    def list_memories(self) -> str:
        """List all memories with their metadata."""
        if not self.memories:
            return "No memories saved yet."

        lines = []
        for name, data in self.memories.items():
            lines.append(f"- {name} [{data['type']}]: {data['description']}")
        return "\n".join(lines)
