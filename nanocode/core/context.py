import logging
import os
from dotenv import load_dotenv

from ..llm import OpenAIClient

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

    def compact_tool_calls(self, messages: list) -> list:
        """Compact tool call results before sending messages to the model."""
        if len(messages) <= self.keep_recent_rounds * 2:
            return messages

        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        compacted = []
        for msg in old_messages:
            if msg.get("role") == "system" or msg.get("role") == "user" or msg.get("role") == "assistant":
                compacted.append(msg)
            elif msg.get("role") == "tool":
                compacted.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "tool_name": msg.get("tool_name", ""),
                        "content": f"Tool {msg.get('tool_name', 'unknown')} used",  # truncate tool call content
                    }
                )
        recent_messages = messages[-(self.keep_recent_rounds * 2) :]
        return compacted + recent_messages

    def compact(self, messages: list) -> list:
        """Automatically compact messages when token count exceeds threshold."""
        if self._token_estimate(messages) <= self.token_threshold:
            return messages

        logger.info("Token count exceeds threshold, compacting messages...")
        # Keep recent rounds, summarize older messages
        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        context = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in old_messages]
        )
        summary_prompt = (
            "Summarize the following conversation for continuity. Keeping important details, include:\n"
            "(1) Current state: what has been done, what is the current situation\n"
            "(2) Key decisions: any important decisions made during the conversation\n"
            "(3) Unresolved questions or tasks: what is still pending or needs attention\n"
            "Again, keeping important details and omitting trivial parts.\n"
            f"\n## Conversation:\n{context}\n\n## Summary:"
        )

        new_messages = [
            {"role": "system", "content": "You are a helpful context manager."},
            {"role": "user", "content": summary_prompt},
        ]
        response = self.client.chat(model="kimi-k2.5", messages=new_messages)
        if not response or not response.choices or len(response.choices) == 0:
            logger.warning("No response from LLM for context compaction. Returning original messages.")
            return messages
        
        summary = response.choices[0].message.content.strip()

        # Return compacted messages with summary + recent messages
        pre_messages = [
            {"role": "user", "content": f"Summary of previous conversation: {summary}"},
            {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
        ]
        return pre_messages + messages[-(self.keep_recent_rounds * 2) :]

    def _token_estimate(self, messages: list) -> int:
        """Estimate token count of messages (rough estimate: 1 token per 4 chars)."""
        return len(str(messages)) // 4
