"""Sub-agent spawning tool."""

import json
import logging
import os

from dotenv import load_dotenv

from ..llm import OpenAIClient
from ..message import AssistantMessage, Message, SystemMessage, ToolCall, ToolCallFunction, ToolMessage, UserMessage
from ..utils import WORK_DIR
from .base import Tool, ToolParams

logger = logging.getLogger(__name__)


class SubAgent(Tool):
    """Spawn a sub-agent with fresh context."""

    PARAMS = ToolParams().param("task", str, description="Task description for the sub-agent").required("task")

    def name(self) -> str:
        return "sub_agent"

    def description(self) -> str:
        return "Spawn a subagent with fresh context to solve a given task. It shares the filesystem but not conversation history."

    def execute(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        logger.info("sub_agent(task=%s)", task)

        if not task:
            return "No task provided for sub-agent."

        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("MODEL", "kimi-2.5")
        client = OpenAIClient(api_key=openai_api_key, base_url=openai_base_url)

        system_prompt = f"You are a coding sub-agent at {WORK_DIR}. Complete a given task and return concise summary. Use available tools to solve it. Prefer tools over prose."
        history: list[Message] = [
            SystemMessage(content=system_prompt),
            UserMessage(content=task),
        ]

        # Import registry here to avoid circular import
        from ..tools import registry

        # Sub-agent loop with limited rounds to prevent infinite recursion
        for _ in range(5):
            response = client.chat(
                model=model,
                messages=history,
                tools=registry.get_schemas_for_subagent(),
                max_tokens=4096,
                temperature=1.0,
                extra_body={"enable_thinking": True},
            )

            message = response.choices[0].message

            if hasattr(message, "reasoning_content") and message.reasoning_content:
                logger.debug(
                    "Sub-agent reasoning content:\n%s\n🤔 sub-agent reasoning content:\n%s\n%s",
                    "=" * 40,
                    message.reasoning_content,
                    "=" * 40,
                )

            if response.choices[0].finish_reason == "tool_calls":
                tool_calls = response.choices[0].message.tool_calls

                for call in tool_calls:
                    if call.function.name in registry.list_tools_for_subagent():
                        args = json.loads(call.function.arguments)
                        output = registry.get_tool(call.function.name).execute(**args)
                        history.append(
                            AssistantMessage(
                                content=message.content or "",
                                tool_calls=[
                                    ToolCall(
                                        id=call.id,
                                        type=call.type,
                                        function=ToolCallFunction(
                                            name=call.function.name,
                                            arguments=call.function.arguments,
                                        ),
                                    )
                                ],
                            )
                        )
                        history.append(
                            ToolMessage(
                                tool_call_id=call.id,
                                tool_name=call.function.name,
                                content=output,
                            )
                        )
            elif response.choices[0].finish_reason == "stop":
                break
            else:
                logger.warning(
                    "Unexpected finish reason in sub-agent: %s",
                    response.choices[0].finish_reason,
                )
                break

        # Only return the final response
        return (
            response.choices[0].message.content.strip()
            if response.choices[0].message.content
            else "Sub-agent finished without response."
        )
