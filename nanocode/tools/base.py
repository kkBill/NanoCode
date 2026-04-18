"""Base Tool abstract class."""
from abc import ABC


class Tool(ABC):
    """Abstract base class for all tools."""

    def name(self) -> str:
        """Return the tool name."""
        raise NotImplementedError

    def description(self) -> str:
        """Return the tool description."""
        raise NotImplementedError

    def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments."""
        raise NotImplementedError

    def schema(self) -> dict:
        """Return the JSON schema for the tool."""
        raise NotImplementedError
