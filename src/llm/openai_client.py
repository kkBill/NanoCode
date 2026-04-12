import time
import random
from openai import (
    OpenAI,
    APIStatusError,
    APIConnectionError,
)
from openai._types import Omit

class OpenAIClient:
    def __init__(self, api_key: str, base_url: str):
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
        temperature: float = 0.7,
        extra_body: dict | None = None,
        retry: int = 3,
        delay: int = 2,
    ):
        for attempt in range(retry):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    # 遵循OpenAI SDK参数规范, 如果tools为None则传递Omit()表示不传递该参数. None不等价于Omit().
                    tools=tools if tools else Omit(),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_body=extra_body,
                )
                return response
            except (APIStatusError, APIConnectionError) as e:
                # TODO 错误信息要写到日志里
                print(f"API error on attempt {attempt + 1}/{retry}: {e}")
                if attempt < retry - 1:
                    backoff_delay = self._backoff_delay(attempt, base_delay=delay)
                    print(f"Retrying in {backoff_delay} seconds...")
                    time.sleep(backoff_delay)
                else:
                    print(f"Max retries ({retry} times) reached. Raising exception.")
                    raise
            except Exception as e:
                print(f"Unexpected error during LLM call: {e}")
                raise

    def _backoff_delay(self, attempt: int, base_delay: int = 2) -> float:
        """
        exponential backoff delay with jitter.
        backoff_delay = base_delay * (2^attempt) + random(0,1)
        """
        return min(base_delay * (2 ** attempt), self.max_delay) + random.uniform(0, 1)
