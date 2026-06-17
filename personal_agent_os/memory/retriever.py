from __future__ import annotations

from typing import Optional

from personal_agent_os.domain import ChatRequest

from .base import MemoryStore


class MemoryRetriever:
    def __init__(self, store: Optional[MemoryStore] = None):
        self.store = store

    async def retrieve(self, request: ChatRequest) -> str:
        if not self.store:
            return ""
        results = await self.store.search(request.query, limit=5)
        return "\n".join(results)
