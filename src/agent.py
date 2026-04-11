"""Main agent loop and orchestration."""
from .config import MEMORY_EXTRACT_INSTRUCTIONS, WORKDIR, MODEL_NAME, client
from .core import (
    hook_manager,
    permission_manager,
    background_manager,
    context_manager,
    memory_manager,
)
from .tools import registry
import json


def build_system_prompt() -> str:
    """Assemble system prompt from different parts."""
    parts = [f"You are a coding agent at {WORKDIR}. Use available and appropriate tools to solve tasks."]

    # Load memories if available
    memories = memory_manager.build_memory_prompt()
    if memories:
        parts.append(memories)

    parts.append(MEMORY_EXTRACT_INSTRUCTIONS)

    return "\n\n".join(parts)


def agent_loop(messages: list):
    """Main agent loop for processing messages and tool calls."""
    # Track how many rounds since last todo update
    round_since_last_todo = 0

    while True:
        # Get all results from background tasks and append to messages
        background_results = [
            f"Task {r['task_id']} finished with status {r['status']}. Command: {r['command']}. Result: {r['result']}"
            for r in background_manager.get_result()
        ]
        results_content = "\n".join(background_results)
        if results_content:
            messages.append({"role": "user", "content": results_content})
            messages.append({"role": "assistant", "content": "Noted background results."})

        messages = context_manager.compact_tool_calls(messages)
        messages = context_manager.compact(messages)

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=registry.get_all_schemas(),
            max_tokens=4096,
            temperature=0.7,
            extra_body={"enable_thinking": True},
        )

        message = response.choices[0].message

        # Print reasoning content if available
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            print("=" * 40)
            print("🤔 reasoning content:")
            print(message.reasoning_content)
            print("=" * 40)

        used_todo = False
        if response.choices[0].finish_reason == "tool_calls":
            tool_calls = response.choices[0].message.tool_calls

            # Convert tool calls to dict format
            tool_call_msg = {"role": "assistant", "content": "", "tool_calls": []}
            for call in tool_calls:
                tool_call_msg["tool_calls"].append(
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"arguments": call.function.arguments, "name": call.function.name}
                    }
                )
            messages.append(tool_call_msg)

            for call in tool_calls:
                # Before_tool_call hook
                ctx = {"tool_name": call.function.name, "tool_args": call.function.arguments}
                hook_result = hook_manager.run_hook("before_tool_call", ctx)

                print(f"hook result: {hook_result}")

                if call.function.name in registry.list_tools():
                    # Check permission
                    decision = permission_manager.check(call.function.name, json.loads(call.function.arguments))
                    output = ""
                    if decision["behavior"] == "deny":
                        output = f"Permission denied. {decision['reason']}"
                        print(f"Permission denied. {decision['reason']}")
                    elif decision["behavior"] == "ask":
                        user_allow = permission_manager.ask_user(call.function.name, call.function.arguments)
                        # user_allow = True
                        if not user_allow:
                            output = f"Permission denied by user for {call.function.name}"
                            print(f"Permission denied by user for {call.function.name}")
                        else:
                            print(f"Permission allowed by user for {call.function.name}")
                            args = json.loads(call.function.arguments)
                            output = registry.get_tool(call.function.name).execute(**args)
                    else:
                        # Permission check passed
                        args = json.loads(call.function.arguments)
                        output = registry.get_tool(call.function.name).execute(**args)

                    # Append tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "tool_name": call.function.name,
                            "content": output,
                        }
                    )

                if call.function.name == "todo":
                    used_todo = True

        elif response.choices[0].finish_reason == "stop":
            print("Final response:", response.choices[0].message.content)
            return response.choices[0].message.content
        else:
            print(f"Unexpected finish reason: {response.choices[0].finish_reason}")
            return f"Unexpected finish reason: {response.choices[0].finish_reason}"

        round_since_last_todo = 0 if used_todo else round_since_last_todo + 1
