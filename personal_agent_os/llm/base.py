from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from .config import LLMConfig
from .types import LLMMessage, LLMTextResult


class LLMClient(ABC):
    """Thin model client boundary: call the model and return text."""

    @abstractmethod
    async def chat(self, messages: Sequence[LLMMessage], config: LLMConfig) -> LLMTextResult:
        raise NotImplementedError
