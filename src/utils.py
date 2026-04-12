"""Utility functions for the agent."""
import json
from pathlib import Path


def debug_print_messages(messages: list):
    """Print messages for debugging purposes."""
    print("-" * 40)
    output = json.dumps(messages, indent=2, ensure_ascii=False)
    print(output)
    print("-" * 40)

def debug_print_reasoning_content(message):
    """Print reasoning content if available."""
    if hasattr(message, "reasoning_content") and message.reasoning_content:
        print("=" * 40)
        print("🤔 reasoning content:")
        print(message.reasoning_content)
        print("=" * 40)

def safe_path(p: str, workdir: Path) -> Path:
    """
    Ensure all file operations are within WORKDIR to prevent path traversal attacks.

    Args:
        p: The path to validate
        workdir: The base working directory

    Returns:
        Resolved Path within workdir

    Raises:
        ValueError: If path escapes the workspace
    """
    path = (workdir / p).resolve()
    # Verify: final path must be within WORKDIR
    if not path.is_relative_to(workdir):
        raise ValueError(f"Path escapes workspace: {p}")

    return path
