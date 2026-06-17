from __future__ import annotations

from typing import Any, Optional

from .adapter import ResonaLegacyAdapter


class LegacyTTSService:
    def __init__(self, legacy_tts_backend: Any, adapter: ResonaLegacyAdapter):
        self.legacy_tts_backend = legacy_tts_backend
        self.adapter = adapter

    async def synthesize(self, text: str, emotion: str = "<E:smile>", language: Optional[str] = None, **kwargs: Any) -> Any:
        synthesize = getattr(self.legacy_tts_backend, "synthesize", None)
        if synthesize is None:
            raise RuntimeError("Legacy TTS backend does not expose synthesize")
        if getattr(synthesize, "__code__", None) and synthesize.__code__.co_flags & 0x80:
            return await synthesize(text, emotion, language=language, **kwargs)
        return await self.adapter.run_blocking(
            synthesize,
            text,
            emotion,
            language=language,
            operation_name="legacy_tts_synthesize",
            **kwargs,
        )
