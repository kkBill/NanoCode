"""Utility functions for the agent."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Base paths
NANOCODE_HOME = Path.home() / ".nanocode"
NANOCODE_HOME.mkdir(exist_ok=True)

ROOT_DIR = Path(__file__).parent.parent.resolve()
NANOCODE_DIR = ROOT_DIR / "nanocode"
SKILLS_DIR = NANOCODE_DIR / "skills"
WORK_DIR = ROOT_DIR / "workspace"
WORK_DIR.mkdir(exist_ok=True)


def debug_print_messages(messages: list):
    """Print messages for debugging purposes."""
    from .message import Message
    data = [msg.model_dump() if isinstance(msg, Message) else msg for msg in messages]
    output = json.dumps(data, indent=2, ensure_ascii=False)
    logger.debug("Messages:\n%s\n%s\n%s", "-" * 40, output, "-" * 40)


def debug_print_reasoning_content(message):
    """Print reasoning content if available."""
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        logger.debug(
            "Reasoning content:\n%s\n%s\n%s",
            "-" * 40,
            message.reasoning_content,
            "-" * 40,
        )


def safe_path(p: str, workdir: Path) -> Path:
    """
    Ensure all file operations are within WORK_DIR to prevent path traversal attacks.

    Args:
        p: The path to validate
        workdir: The base working directory

    Returns:
        Resolved Path within workdir

    Raises:
        ValueError: If path escapes the workspace
    """
    path = (workdir / p).resolve()
    # Verify: final path must be within WORK_DIR
    if not path.is_relative_to(workdir):
        raise ValueError(f"Path escapes workspace: {p}")

    return path
