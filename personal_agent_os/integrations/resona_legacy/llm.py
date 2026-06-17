from __future__ import annotations

from typing import Any

from .adapter import ResonaLegacyAdapter


class LegacyLLMClient:
    def __init__(self, legacy_backend: Any, adapter: ResonaLegacyAdapter):
        self.legacy_backend = legacy_backend
        self.adapter = adapter

    async def query(self, question: str, **kwargs: Any) -> Any:
        async_query = getattr(self.legacy_backend, "query", None)
        if async_query is None:
            raise RuntimeError("Legacy LLM backend does not expose query")
        if getattr(async_query, "__code__", None) and async_query.__code__.co_flags & 0x80:
            return await async_query(question, **kwargs)
        return await self.adapter.run_blocking(async_query, question, operation_name="legacy_llm_query", **kwargs)
