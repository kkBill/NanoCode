import logging
import random
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    OpenAI,
)
from openai._types import Omit

from ..message import Message

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str | None, base_url: str | None):
        if not api_key:
            raise ValueError("API key is required for OpenAIClient.")
        if not base_url:
            raise ValueError("Base URL is required for OpenAIClient.")

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_delay = 60  # Max delay of 1 minute for retries

    def chat(
        self,
        model: str,
        messages: list,
        tools: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        extra_body: dict | None = None,
        retry: int = 3,
        delay: int = 2,
    ):
        # Normalize Message objects to plain dicts for the OpenAI SDK
        dict_messages = [msg.to_dict() if isinstance(msg, Message) else msg for msg in messages]

        for attempt in range(retry):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=dict_messages,
                    # 遵循OpenAI SDK参数规范, 如果tools为None则传递Omit()表示不传递该参数. None不等价于Omit().
                    tools=tools if tools else Omit(),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_body=extra_body,
                )
                return response
            except (APIStatusError, APIConnectionError) as e:
                logger.error("API error on attempt %d/%d: %s", attempt + 1, retry, e)
                if attempt < retry - 1:
                    backoff_delay = self._backoff_delay(attempt, base_delay=delay)
                    logger.info("Retrying in %.1f seconds...", backoff_delay)
                    time.sleep(backoff_delay)
                else:
                    logger.error("Max retries (%d times) reached. Raising exception.", retry)
                    raise
            except Exception as e:
                logger.exception("Unexpected error during LLM call: %s", e)
                raise

    def _backoff_delay(self, attempt: int, base_delay: int = 2) -> float:
        """
        exponential backoff delay with jitter.
        backoff_delay = base_delay * (2^attempt) + random(0,1)
        """
        return min(base_delay * (2**attempt), self.max_delay) + random.uniform(0, 1)
