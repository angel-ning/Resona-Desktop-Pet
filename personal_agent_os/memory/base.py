from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class MemoryStore(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[str]:
        raise NotImplementedError
