from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from personal_agent_os.domain import ToolCall, ToolManifest, ToolResult


class ToolProvider(ABC):
    @abstractmethod
    def list_tools(self) -> List[ToolManifest]:
        raise NotImplementedError

    @abstractmethod
    async def call_tool(self, call: ToolCall) -> ToolResult:
        raise NotImplementedError


class EmptyToolProvider(ToolProvider):
    def list_tools(self) -> List[ToolManifest]:
        return []

    async def call_tool(self, call: ToolCall) -> ToolResult:
        return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, error="Tool not found")
