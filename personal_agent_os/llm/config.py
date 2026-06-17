from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 800

    @classmethod
    def from_env(cls) -> Optional["LLMConfig"]:
        model = os.getenv("AGENT_OS_MODEL", "").strip()
        if not model:
            return None

        temperature_raw = os.getenv("AGENT_OS_TEMPERATURE", "0.7").strip()
        max_tokens_raw = os.getenv("AGENT_OS_MAX_TOKENS", "800").strip()
        top_p_raw = os.getenv("AGENT_OS_TOP_P", "1.0").strip()
        try:
            temperature = float(temperature_raw)
        except ValueError:
            temperature = 0.7
        try:
            top_p = float(top_p_raw)
        except ValueError:
            top_p = 1.0
        try:
            max_tokens = int(max_tokens_raw)
        except ValueError:
            max_tokens = 800

        return cls(
            model=model,
            api_key=os.getenv("AGENT_OS_API_KEY") or None,
            base_url=os.getenv("AGENT_OS_BASE_URL") or None,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
