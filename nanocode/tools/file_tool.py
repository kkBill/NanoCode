"""File I/O tools."""

import logging

from ..utils import WORK_DIR, safe_path
from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class ReadFile(Tool):
    """Read file contents."""

    PARAMS = ToolParams().param("filename", str, description="Path to the file to read").required("filename")

    def name(self) -> str:
        return "read_file"

    def description(self) -> str:
        return "Read a file's content."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        logger.info("read_file(%s)", path)

        try:
            real_path = safe_path(path, WORK_DIR)
            content = real_path.read_text(encoding="utf-8")
            return content[:50000] if content else "(empty file)"
        except Exception as e:
            return f"Error: {str(e)}"


class WriteFile(Tool):
    """Write content to files."""

    PARAMS = (
        ToolParams()
        .param("filename", str, description="Path to the file to write")
        .param("content", str, description="Content to write into the file")
        .required("filename", "content")
    )

    def name(self) -> str:
        return "write_file"

    def description(self) -> str:
        return "Write content to a file."

    def execute(self, **kwargs) -> str:
        path = kwargs.get("filename", "")
        content = kwargs.get("content", "")
        logger.info("write_file(%s, content length=%d)", path, len(content))

        try:
            real_path = safe_path(path, WORK_DIR)
            real_path.write_text(content)
            return "File written successfully"
        except Exception as e:
            return f"Error: {str(e)}"
