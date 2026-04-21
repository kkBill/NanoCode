from abc import ABC, abstractmethod
from typing import Any, ClassVar, Self


class ToolParams:
    """链式构建 OpenAI function parameters schema。"""

    _TYPE_MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    def __init__(self):
        self._properties: dict = {}
        self._required: list[str] = []

    def param(
        self,
        name: str,
        type_: type | str,
        *,
        description: str | None = None,
        enum: list[str] | None = None,
        items: type | str | None = None,
        **extra,
    ) -> Self:
        """声明一个参数。type_ 接受 Python 内置类型或 JSON Schema 类型字符串。"""
        json_type = self._resolve_type(type_)
        prop: dict[str, Any] = {"type": json_type}
        if description:
            prop["description"] = description
        if enum:
            prop["enum"] = enum
        if json_type == "array" and items is not None:
            prop["items"] = {"type": self._resolve_type(items)}
        prop.update(extra)
        self._properties[name] = prop
        return self

    def required(self, *names: str) -> Self:
        """标记必填参数。不传表示无必填项。"""
        self._required.extend(names)
        return self

    def build(self) -> tuple[dict, list[str] | None]:
        """返回 (properties, required)。基类用这两个值拼装最终结构。"""
        return self._properties, self._required if self._required else None

    def _resolve_type(self, t: type | str) -> str:
        if isinstance(t, str):
            return t
        if mapped := self._TYPE_MAP.get(t):
            return mapped
        raise ValueError(f"Unsupported type: {t}. Use str, int, float, bool, list, dict, or a string.")


class Tool(ABC):
    """Abstract base class for all tools."""

    # Subclasses declare parameters via ToolParams chain builder.
    # Leave undefined or set to None for tools with no parameters.
    PARAMS: ClassVar = None

    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""

    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given arguments."""

    def schema(self) -> dict:
        """Return the JSON schema for the tool.

        Builds the standard OpenAI function-calling schema from PARAMS.
        Subclasses may override if they need a non-standard schema.
        """
        if self.PARAMS is None:
            properties, required = {}, None
        else:
            properties, required = self.PARAMS.build()

        params = {"type": "object", "properties": properties}
        if required:
            params["required"] = required

        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": params,
            },
        }
