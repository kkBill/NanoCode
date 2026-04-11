"""Sub-agent spawning tool."""
import json

from ..config import client, MODEL_NAME, WORKDIR
from .base import Tool


class SubAgent(Tool):
    """Spawn a sub-agent with fresh context."""

    def name(self) -> str:
        return "sub_agent"

    def description(self) -> str:
        return "Spawn a subagent with fresh context to solve a given task. It shares the filesystem but not conversation history."

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                    },
                    "required": ["task"],
                },
            },
        }

    def execute(self, **kwargs) -> str:
        task = kwargs.get("task", "")
        print(f"sub_agent(task={task})")

        if not task:
            return "No task provided for sub-agent."

        system_prompt = f"You are a coding sub-agent at {WORKDIR}. Complete a given task and return concise summary. Use available tools to solve it. Prefer tools over prose."
        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        # Import registry here to avoid circular import
        from ..tools import registry

        # Sub-agent loop with limited rounds to prevent infinite recursion
        for _ in range(5):
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=history,
                tools=registry.get_schemas_for_subagent(),
                max_tokens=4096,
                temperature=0.7,
                extra_body={"enable_thinking": True},
            )

            message = response.choices[0].message

            if hasattr(message, "reasoning_content") and message.reasoning_content:
                print("=" * 40)
                print("🤔 sub-agent reasoning content:")
                print(message.reasoning_content)
                print("=" * 40)

            if response.choices[0].finish_reason == "tool_calls":
                tool_calls = response.choices[0].message.tool_calls

                for call in tool_calls:
                    if call.function.name in registry.list_tools_for_subagent():
                        args = json.loads(call.function.arguments)
                        output = registry.get_tool(call.function.name).execute(**args)
                        history.append(
                            {
                                "role": "assistant",
                                "content": message.content,
                                "tool_calls": [
                                    {
                                        "id": call.id,
                                        "type": "function",
                                        "function": {
                                            "name": call.function.name,
                                            "arguments": call.function.arguments,
                                        },
                                    }
                                ],
                            }
                        )
                        history.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "tool_name": call.function.name,
                                "content": output,
                            }
                        )
            elif response.choices[0].finish_reason == "stop":
                break
            else:
                print(
                    f"Unexpected finish reason in sub-agent: {response.choices[0].finish_reason}"
                )
                break

        # Only return the final response
        return (
            response.choices[0].message.content.strip()
            if response.choices[0].message.content
            else "Sub-agent finished without response."
        )
