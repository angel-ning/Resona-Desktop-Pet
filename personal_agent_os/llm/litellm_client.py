from __future__ import annotations

import time
from typing import Any, Sequence

from litellm import acompletion

from personal_agent_os.infrastructure.logging import get_logger

from .base import LLMClient
from .config import LLMConfig
from .types import LLMMessage, LLMTextResult

logger = get_logger("llm")


class LiteLLMClient(LLMClient):
    async def chat(self, messages: Sequence[LLMMessage], config: LLMConfig) -> LLMTextResult:
        started_at = time.perf_counter()
        logger.info("LiteLLM chat start model=%s message_count=%s", config.model, len(messages))
        response = await acompletion(
            model=config.model,
            messages=[message.to_dict() for message in messages],
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        text = self._extract_text(response)
        logger.info("LiteLLM chat complete model=%s elapsed_ms=%s text_chars=%s", config.model, elapsed_ms, len(text))
        return LLMTextResult(
            text=text,
            model=config.model,
            raw=response,
            metadata={"elapsed_ms": elapsed_ms},
        )

    def _extract_text(self, response: Any) -> str:
        choices = response.get("choices", []) if isinstance(response, dict) else getattr(response, "choices", [])
        if not choices:
            return ""
        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else getattr(first, "message", None)
        if isinstance(message, dict):
            content = message.get("content") or ""
        else:
            content = getattr(message, "content", "") if message is not None else ""
        return content if isinstance(content, str) else str(content)
