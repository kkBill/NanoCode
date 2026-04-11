"""Context management for message compaction."""
from ..config import client, MODEL_NAME


class ContextManager:
    """Manage context window and message compaction."""

    def __init__(self, token_threshold: int = 1024, keep_recent_rounds: int = 1):
        self.token_threshold = token_threshold
        self.keep_recent_rounds = keep_recent_rounds

    def compact_tool_calls(self, messages: list) -> list:
        """Compact tool call results before sending messages to the model."""
        if len(messages) <= self.keep_recent_rounds * 2:
            return messages

        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        compacted = []
        for msg in old_messages:
            if msg.get("role") == "system" or msg.get("role") == "user":
                compacted.append(msg)
            elif msg.get("role") == "assistant" and "tool_calls" not in msg:
                compacted.append(msg)
            elif msg.get("role") == "tool":
                # For tool messages, only keep the tool name
                compacted.append(
                    {
                        "role": "assistant",
                        "content": f"Tool {msg.get('tool_name', 'unknown')} used",
                    }
                )
        recent_messages = messages[-(self.keep_recent_rounds * 2) :]
        return compacted + recent_messages

    def compact(self, messages: list) -> list:
        """Automatically compact messages when token count exceeds threshold."""
        if self._token_estimate(messages) <= self.token_threshold:
            return messages

        print("Token count exceeds threshold, compacting messages...")
        # Keep recent rounds, summarize older messages
        old_messages = messages[: -(self.keep_recent_rounds * 2)]
        context = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in old_messages]
        )

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful context manager. Summarize the following conversation history in a concise way, keeping important details and omitting trivial parts.",
                },
                {"role": "user", "content": context},
            ],
            max_tokens=1024,
            temperature=0.5,
        )
        summary = response.choices[0].message.content.strip()

        # Return compacted messages with summary + recent messages
        pre_messages = [
            {"role": "user", "content": f"Summary of previous conversation: {summary}"},
            {
                "role": "assistant",
                "content": "Understood. I have the context from the summary. Continuing.",
            },
        ]
        return pre_messages + messages[-(self.keep_recent_rounds * 2) :]

    def _token_estimate(self, messages: list) -> int:
        """Estimate token count of messages (rough estimate: 1 token per 4 chars)."""
        return len(str(messages)) // 4
