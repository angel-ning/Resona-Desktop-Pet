from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from personal_agent_os.domain import ClientCapabilities, ToolCall, ToolManifest, ToolResult
from personal_agent_os.infrastructure.logging import bind_log_context, clear_log_context, get_logger

from .base import EmptyToolProvider, ToolProvider
from .capabilities import CapabilityGuard

logger = get_logger("tools")


class ToolRouter:
    def __init__(self, providers: Optional[Iterable[ToolProvider]] = None, guard: Optional[CapabilityGuard] = None):
        self.providers: List[ToolProvider] = list(providers or [EmptyToolProvider()])
        self.guard = guard or CapabilityGuard()

    def list_tools(self) -> List[ToolManifest]:
        tools: List[ToolManifest] = []
        for provider in self.providers:
            tools.extend(provider.list_tools())
        return tools

    def _index(self) -> Dict[str, tuple[ToolManifest, ToolProvider]]:
        index: Dict[str, tuple[ToolManifest, ToolProvider]] = {}
        for provider in self.providers:
            for manifest in provider.list_tools():
                index[manifest.name] = (manifest, provider)
        return index

    async def call_tool(self, call: ToolCall, capabilities: ClientCapabilities) -> ToolResult:
        tokens = bind_log_context(tool_call_id=call.tool_call_id)
        try:
            index = self._index()
            entry = index.get(call.name)
            if not entry:
                logger.warning("Tool not found: %s", call.name)
                return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, error="Tool not found")
            manifest, provider = entry
            blocked = self.guard.check(manifest, capabilities)
            if blocked:
                logger.info("Tool blocked by capabilities: %s missing=%s", call.name, blocked.missing_capabilities)
                return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, blocked=blocked)
            logger.info("Calling tool: %s", call.name)
            result = await provider.call_tool(call)
            logger.info("Tool completed: %s ok=%s", call.name, result.ok)
            return result
        finally:
            clear_log_context(tokens)
