"""Main agent loop and orchestration."""

import logging
import os
import json
from dotenv import load_dotenv

from openai.types.chat import ChatCompletion

from nanocode.core import cron

from .utils import debug_print_messages, debug_print_reasoning_content
from .core import (
    hook_manager,
    permission_manager,
    background_manager,
    context_manager,
    memory_manager,
    cron_scheduler,
)
from .tools import registry
from .llm import OpenAIClient
from .message import (
    Message,
    AssistantMessage,
    ToolMessage,
    UserMessage,
    ToolCall,
    ToolCallFunction,
)

logger = logging.getLogger(__name__)


def agent_loop(messages: list[Message]):
    """Main agent loop"""
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("MODEL", "kimi-k2.5")
    client = OpenAIClient(api_key=openai_api_key, base_url=openai_base_url)

    # 用于控制finish_reason为length时的续写次数，避免无限续写
    continuation_count = 0
    max_continuations = 3

    while True:
        # Get all results from background tasks and append to messages
        background_results = [
            f"Task {r['task_id']} finished with status {r['status']}. Command: {r['command']}. Result: {r['result']}"
            for r in background_manager.get_result()
        ]
        results_content = "\n".join(background_results)
        if results_content:
            messages.append(UserMessage(content=results_content))
            messages.append(AssistantMessage(content="Noted background results."))

        cron_tasks: list[cron.CronTask] = cron_scheduler.drain_notify_queue()
        cron_results = [
            f"Cron task {t.id} triggered. Prompt: {t.prompt}." for t in cron_tasks
        ]
        cron_results_content = "\n".join(cron_results)
        if cron_results_content:
            messages.append(UserMessage(content=cron_results_content))

        # Compact messages to fit within token limits (in-place mutation)
        context_manager.compact_tool_calls(messages)
        context_manager.compact(messages)

        # Print completed messages for debugging
        debug_print_messages(messages)

        # LLM call
        response = client.chat(
            model=model,
            messages=messages,
            tools=registry.get_all_schemas(),
            extra_body={"enable_thinking": True},
        )
        if not response or not response.choices or len(response.choices) == 0:
            logger.warning("No response from LLM call.")
            continue

        # Print reasoning content for debugging
        debug_print_reasoning_content(response.choices[0].message)

        finish_reason = response.choices[0].finish_reason

        if finish_reason == "tool_calls":
            # The most important part in agent loop
            handle_tool_calls(response, messages)
        elif finish_reason == "length":
            # Response meet the max_tokens limit
            """
            [NOTE]
            "length" 表示模型的输出由于达到 max_tokens 上限而被截断, 从本质上讲, 这只表明模型的输出“到了篇幅上限”, 而不是“发生了错误”,
            因此, 可以把截断的内容加回 messages, 并再注入一条提示, 让模型接着上文继续生成, 直到模型输出 "stop" 或者达到最大续写次数为止
            但这仅是一种权宜之计, 存在很多局限性, 此处仅供学习.

            业界主流的解决方法是从根本上避免触发 length, 而不是依赖续写来补救。包括:
            - 提高 max_tokens, 遇到 length 时提示用户并直接返回截断内容
            - 对上下文进行压缩
            - 对任务进行分解, 使每次调用只做一件小事
            """
            continuation_count += 1
            if continuation_count > max_continuations:
                logger.error(
                    "Maximum continuations reached (%d). Stopping further continuations.",
                    max_continuations,
                )
                return "Response was too long and maximum continuations reached."
            else:
                logger.info(
                    "Response was cut off due to length. Attempting continuation %d/%d...",
                    continuation_count,
                    max_continuations,
                )
                # Append the truncated content back to messages and prompt for continuation
                truncated_content = response.choices[0].message.content
                messages.append(AssistantMessage(content=truncated_content))
                messages.append(UserMessage(content="The previous response was cut off due to length. Please continue from where you left off."))
        elif finish_reason == "stop":
            # Normal finish, return the content to user and end the loop
            logger.info("Final response: %s", response.choices[0].message.content)
            return response.choices[0].message.content
        else:
            logger.warning("Unexpected finish reason: %s", finish_reason)
            return f"Unexpected finish reason: {finish_reason}"


def handle_tool_calls(response: ChatCompletion, messages: list[Message]):
    """
    Handle tool calls in the response.

    Response with tool calls is as follows:
    ```json
    {
        "finish_reason": "tool_calls",
        "message": {
            "content": "",
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "search:0",
                    "type": "function",
                    "function": {
                        "arguments": "{\n\"query\": \"xxxxxx\"\n}",
                        "name": "search"
                    },
                }
            ]
        }
    }
    ```
    """
    message = response.choices[0].message
    tool_calls = message.tool_calls
    if not tool_calls or len(tool_calls) == 0:
        # TODO
        # 是否存在finish_reason是tool_calls但是没有tool_calls字段的情况？
        # 如果有，这种情况应该怎么处理？目前先简单地打印日志并返回。
        logger.warning("No tool calls found in the message.")
        return

    # Convert tool calls to ToolCall objects and append to messages history
    tool_call_list = [
        ToolCall(
            id=call.id,
            type=call.type,
            function=ToolCallFunction(
                name=call.function.name,
                arguments=call.function.arguments,
            ),
        )
        for call in tool_calls
    ]
    assistant_msg = AssistantMessage(
        content=message.content or "",
        tool_calls=tool_call_list,
        reasoning_content=getattr(message, "reasoning_content", "") or "",
    )
    messages.append(assistant_msg)

    for call in tool_calls:
        call_id = call.id
        tool_name = call.function.name  # type: ignore
        tool_args = call.function.arguments  # type: ignore

        if tool_name not in registry.list_tools():
            logger.warning("Tool %s not found.", tool_name)
            output = f"Tool {tool_name} not found."
            messages.append(ToolMessage(tool_call_id=call_id, tool_name=tool_name, content=output))
            continue

        # handle 'before_tool_call' event before tool call execution
        handle_hook("before_tool_call", tool_name, tool_args)

        # check permission
        if handle_permission_check(tool_name, tool_args):
            args = json.loads(tool_args)
            tool = registry.get_tool(tool_name)
            output = tool.execute(**args) if tool else f"Tool {tool_name} not found."
        else:
            # need to return denied output to the model so that it can adjust its plan accordingly
            output = f"Permission denied for tool {tool_name} with args {tool_args}"

        # append tool call result to messages history
        messages.append(ToolMessage(tool_call_id=call_id, tool_name=tool_name, content=output))


# TODO
# hook调用，需要重构
# 如果hook调用失败，是否会阻断主agent的执行？
# 是否需要把hook调用的结果返回给模型？比如，用户在'before_send_llm'这个hook里进行prompt注入，如何把这些信息返回给模型？
def handle_hook(event: str, tool_name: str, tool_args: str):
    """
    Handle lifecycle hooks.

    Hooks are custom logic that can be executed at specific points in the agent's operation,
    such as before or after a tool call, or before sending messages to the LLM.
    """
    ctx = {"tool_name": tool_name, "tool_args": tool_args}
    hook_result = hook_manager.run_hook(event, ctx)
    logger.debug("hook result: %s", hook_result)


def handle_permission_check(tool_name: str, tool_args: str) -> bool:
    """
    Handle permission check for a tool call.

    This function checks if the tool call is allowed based on predefined rules or by asking the user.
    """
    # decision = permission_manager.check(tool_name, json.loads(tool_args))

    # if decision["behavior"] == "deny":
    #     print(f"Permission denied. {decision['reason']}")
    #     return False

    # if decision["behavior"] == "ask":
    #     user_allowed = permission_manager.ask_user(tool_name, json.loads(tool_args))
    #     if not user_allowed:
    #         print(f"Permission denied by user for {tool_name}")
    #         return False
    #     else:
    #         print(f"Permission allowed by user for {tool_name}")
    #         return True

    # decision["behavior"] == "allow", permission check passed
    return True
