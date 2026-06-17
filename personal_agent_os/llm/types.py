from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

LLMRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LLMTextResult:
    text: str
    model: str
    raw: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
