"""File I/O tools."""
from ..utils import safe_path
from ..config import WORKDIR
from .base import Tool


class ReadFile(Tool):
    """Read file contents."""

    def name(self) -> str:
        return "read_file"

    def description(self) -> str:
        return "Read a file's content."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        print(f"read_file({path})")

        try:
            real_path = safe_path(path, WORKDIR)
            content = real_path.read_text(encoding="utf-8")
            return content[:50000] if content else "(empty file)"
        except Exception as e:
            return f"Error: {str(e)}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {"filename": {"type": "string"}},
                    "required": ["filename"],
                },
            },
        }


class WriteFile(Tool):
    """Write content to files."""

    def name(self) -> str:
        return "write_file"

    def description(self) -> str:
        return "Write content to a file."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        content = kwargs.get("content", "")
        print(f"write_file({path}, content length={len(content)})")

        try:
            real_path = safe_path(path, WORKDIR)
            real_path.write_text(content)
            return "File written successfully"
        except Exception as e:
            return f"Error: {str(e)}"

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["filename", "content"],
                },
            },
        }
