from __future__ import annotations

from typing import Any, List

from personal_agent_os.domain import ToolCall, ToolManifest, ToolResult
from personal_agent_os.tools import ToolProvider

from .adapter import ResonaLegacyAdapter


class LegacyMCPToolProvider(ToolProvider):
    def __init__(self, legacy_mcp_manager: Any, adapter: ResonaLegacyAdapter):
        self.legacy_mcp_manager = legacy_mcp_manager
        self.adapter = adapter

    def list_tools(self) -> List[ToolManifest]:
        raw_tools = self.legacy_mcp_manager.get_tools(public_only=True)
        manifests: List[ToolManifest] = []
        for raw in raw_tools:
            function = raw.get("function", raw)
            name = function.get("name")
            if not name:
                continue
            manifests.append(
                ToolManifest(
                    name=name,
                    description=function.get("description", ""),
                    input_schema=function.get("parameters", {}),
                    provider="legacy_mcp",
                    required_capabilities=self._infer_required_capabilities(name, function.get("description", "")),
                )
            )
        return manifests

    async def call_tool(self, call: ToolCall) -> ToolResult:
        async_call = getattr(self.legacy_mcp_manager, "call_tool")
        try:
            if getattr(async_call, "__code__", None) and async_call.__code__.co_flags & 0x80:
                content = await async_call(call.name, call.arguments)
            else:
                content = await self.adapter.run_blocking(
                    async_call,
                    call.name,
                    call.arguments,
                    operation_name=f"legacy_mcp_tool:{call.name}",
                )
            return ToolResult(ok=True, name=call.name, tool_call_id=call.tool_call_id, content=content)
        except Exception as exc:
            return ToolResult(ok=False, name=call.name, tool_call_id=call.tool_call_id, error=str(exc))

    def _infer_required_capabilities(self, name: str, description: str) -> List[str]:
        text = f"{name} {description}".lower()
        required: List[str] = []
        if any(token in text for token in ["write", "edit", "delete", "filesystem", "file"]):
            required.append("allow_fs_write")
        if any(token in text for token in ["read", "search file"]):
            required.append("allow_fs_read")
        if any(token in text for token in ["shell", "command", "powershell", "exec"]):
            required.append("allow_shell")
        if any(token in text for token in ["desktop", "window", "mouse", "keyboard"]):
            required.append("allow_desktop_control")
        return list(dict.fromkeys(required))
