from __future__ import annotations

from typing import Any

from .adapter import ResonaLegacyAdapter


class LegacySTTService:
    def __init__(self, legacy_stt_backend: Any, adapter: ResonaLegacyAdapter):
        self.legacy_stt_backend = legacy_stt_backend
        self.adapter = adapter

    async def transcribe(self, *args: Any, **kwargs: Any) -> Any:
        transcribe = getattr(self.legacy_stt_backend, "transcribe", None) or getattr(self.legacy_stt_backend, "recognize", None)
        if transcribe is None:
            raise RuntimeError("Legacy STT backend does not expose transcribe/recognize")
        if getattr(transcribe, "__code__", None) and transcribe.__code__.co_flags & 0x80:
            return await transcribe(*args, **kwargs)
        return await self.adapter.run_blocking(transcribe, *args, operation_name="legacy_stt_transcribe", **kwargs)
