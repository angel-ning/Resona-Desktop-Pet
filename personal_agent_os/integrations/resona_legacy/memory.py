from __future__ import annotations

from typing import Any, List

from personal_agent_os.memory import MemoryStore

from .adapter import ResonaLegacyAdapter


class LegacyMemoryStore(MemoryStore):
    def __init__(self, legacy_memory_manager: Any, adapter: ResonaLegacyAdapter, pack_id: str = "default"):
        self.legacy_memory_manager = legacy_memory_manager
        self.adapter = adapter
        self.pack_id = pack_id

    async def search(self, query: str, limit: int = 5) -> List[str]:
        def search_memories() -> List[str]:
            rows = self.legacy_memory_manager.search_memories(self.pack_id, query, limit)
            return [str(row.get("content", row)) for row in rows]

        return await self.adapter.run_blocking(search_memories, operation_name="legacy_memory_search")
