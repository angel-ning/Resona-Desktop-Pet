from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List

from personal_agent_os.domain import ToolCall, ToolManifest, ToolResult

from .base import ToolProvider

ToolFunction = Callable[..., Any] | Callable[..., Awaitable[Any]]


class FunctionToolProvider(ToolProvider):
    def __init__(self):
        self._functions: Dict[str, ToolFunction] = {}
        self._manifests: Dict[str, ToolManifest] = {}

    def register(self, manifest: ToolManifest, func: ToolFunction) -> None:
        self._manifests[manifest.name] = manifest
        self._functions[manifest.name] = func

    def list_tools(self) -> List[ToolManifest]:
        return list(self._manifests.values())

    async def call_tool(self, call: ToolCall) -> ToolResult:
        func = self._functions.get(call.name)
        if not func:
            return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, error="Tool not found")
        try:
            value = func(**call.arguments)
            if inspect.isawaitable(value):
                value = await value
            return ToolResult(ok=True, name=call.name, tool_call_id=call.tool_call_id, content=value)
        except Exception as exc:
            return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, error=str(exc))
