import logging
import os
from dotenv import load_dotenv

from ..llm import OpenAIClient
from ..message import Message, SystemMessage, UserMessage, AssistantMessage, ToolMessage

logger = logging.getLogger(__name__)

class ContextManager:
    """Manage context window and message compaction."""

    def __init__(self, token_threshold: int = 4096, keep_recent_rounds: int = 1):
        self.token_threshold = token_threshold
        self.keep_recent_rounds = keep_recent_rounds
        # TODO 待重构
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        self.client = OpenAIClient(api_key=openai_api_key, base_url=openai_base_url)

    def compact_tool_calls(self, messages: list[Message]) -> None:
        """Compact tool call results before sending messages to the model (in-place)."""
        if len(messages) <= self.keep_recent_rounds * 2:
            return

        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        compacted: list[Message] = []
        for msg in old_messages:
            if isinstance(msg, (SystemMessage, UserMessage, AssistantMessage)):
                compacted.append(msg)
            elif isinstance(msg, ToolMessage):
                compacted.append(
                    ToolMessage(
                        tool_call_id=msg.tool_call_id,
                        tool_name=msg.tool_name,
                        content=f"Tool {msg.tool_name or 'unknown'} used",  # truncate tool call content
                    )
                )
        recent_messages = messages[-(self.keep_recent_rounds * 2) :]
        messages[:] = compacted + recent_messages

    def compact(self, messages: list[Message]) -> None:
        """Automatically compact messages when token count exceeds threshold (in-place)."""
        if self._token_estimate(messages) <= self.token_threshold:
            return

        logger.info("Token count exceeds threshold, compacting messages...")
        # Keep recent rounds, summarize older messages
        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        context = "\n".join(
            [f"{msg.role}: {msg.content}" for msg in old_messages]
        )
        summary_prompt = (
            "Summarize the following conversation for continuity. Keeping important details, include:\n"
            "(1) Current state: what has been done, what is the current situation\n"
            "(2) Key decisions: any important decisions made during the conversation\n"
            "(3) Unresolved questions or tasks: what is still pending or needs attention\n"
            "Again, keeping important details and omitting trivial parts.\n"
            f"\n## Conversation:\n{context}\n\n## Summary:"
        )

        new_messages: list[Message] = [
            SystemMessage(content="You are a helpful context manager."),
            UserMessage(content=summary_prompt),
        ]
        response = self.client.chat(model="kimi-k2.5", messages=new_messages)
        if not response or not response.choices or len(response.choices) == 0:
            logger.warning("No response from LLM for context compaction. Returning original messages.")
            return

        summary = response.choices[0].message.content.strip()

        # Replace messages in-place with summary + recent messages
        pre_messages: list[Message] = [
            UserMessage(content=f"Summary of previous conversation: {summary}"),
            AssistantMessage(content="Understood. I have the context from the summary. Continuing."),
        ]
        messages[:] = pre_messages + messages[-(self.keep_recent_rounds * 2) :]

    def _token_estimate(self, messages: list[Message]) -> int:
        """Estimate token count of messages (rough estimate: 1 token per 4 chars)."""
        return len(str(messages)) // 4
