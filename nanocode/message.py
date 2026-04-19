"""Message types for LLM conversations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallFunction(BaseModel):
    """Function details within a tool call."""

    name: str
    arguments: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "arguments": self.arguments}


class ToolCall(BaseModel):
    """Represents a single tool call in an assistant message."""

    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": self.function.to_dict(),
        }


class Message(BaseModel):
    """Base class for all messages."""

    model_config = ConfigDict(extra="ignore")

    role: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI SDK compatible dict.

        Subclasses should override this to handle role-specific fields.
        Custom fields (e.g., tool_name, reasoning_content) must be excluded.
        """
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Factory: parse a plain dict into the correct Message subclass."""
        role = data.get("role")
        if role == "system":
            return SystemMessage.model_validate(data)
        if role == "user":
            return UserMessage.model_validate(data)
        if role == "assistant":
            return AssistantMessage.model_validate(data)
        if role == "tool":
            return ToolMessage.model_validate(data)
        raise ValueError(f"Unknown message role: {role}")


class SystemMessage(Message):
    """System prompt message."""

    role: Literal["system"] = "system"

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}


class UserMessage(Message):
    """User input message."""

    role: Literal["user"] = "user"

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}


class AssistantMessage(Message):
    """Assistant response message."""

    role: Literal["assistant"] = "assistant"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.reasoning_content:
            result["reasoning_content"] = self.reasoning_content
        return result


class ToolMessage(Message):
    """Tool execution result message."""

    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
        }
