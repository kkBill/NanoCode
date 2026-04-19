from abc import ABC, abstractmethod

class Tool(ABC):
    """Abstract base class for all tools."""

    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""

    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""

    @abstractmethod
    def schema(self) -> dict:
        """Return the JSON schema for the tool."""

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments."""
