from __future__ import annotations

import logging
import uuid
from typing import Awaitable, Callable, Optional

from .contracts import ToolInvocation, ToolResult
from .tool_policy import ToolPolicy

logger = logging.getLogger("AgentOS.ToolExecutor")

SubagentRunner = Callable[[str, str, Optional[str]], Awaitable[str]]


class ToolExecutionService:
    """Deterministic runtime executor for tool calls.

    The LLM can suggest or emit a tool call during the compatibility period, but
    this service is the boundary that decides whether a call reaches MCP.
    """

    def __init__(self, mcp_manager=None, policy: Optional[ToolPolicy] = None):
        self.mcp_manager = mcp_manager
        self.policy = policy or ToolPolicy()

    async def execute(
        self,
        invocation: ToolInvocation,
        subagent_runner: Optional[SubagentRunner] = None,
    ) -> ToolResult:
        decision = self.policy.evaluate(invocation)
        if decision.requires_confirmation:
            logger.info("[AgentOS] Tool requires confirmation: %s", decision.to_dict())
            return ToolResult(
                tool_name=invocation.tool_name,
                status="requires_confirmation",
                policy_reason=decision.reason,
                requires_confirmation=True,
                confirmation_id=f"confirm_{uuid.uuid4().hex}",
            )
        if not decision.allowed:
            logger.warning("[AgentOS] Tool blocked: %s", decision.to_dict())
            return ToolResult(
                tool_name=invocation.tool_name,
                status="policy_blocked",
                policy_reason=decision.reason,
            )

        return await self._execute_allowed(invocation, subagent_runner)

    async def execute_confirmed(
        self,
        invocation: ToolInvocation,
        subagent_runner: Optional[SubagentRunner] = None,
    ) -> ToolResult:
        decision = self.policy.evaluate(invocation)
        if not decision.allowed and not decision.requires_confirmation:
            logger.warning("[AgentOS] Confirmed tool blocked: %s", decision.to_dict())
            return ToolResult(
                tool_name=invocation.tool_name,
                status="policy_blocked",
                policy_reason=decision.reason,
            )
        return await self._execute_allowed(invocation, subagent_runner)

    async def _execute_allowed(
        self,
        invocation: ToolInvocation,
        subagent_runner: Optional[SubagentRunner] = None,
    ) -> ToolResult:
        if not self.mcp_manager:
            return ToolResult(
                tool_name=invocation.tool_name,
                status="tool_error",
                error="MCP manager is not available.",
            )

        tool_meta = self.mcp_manager.get_tool_metadata(invocation.tool_name)
        try:
            if tool_meta.get("subagent"):
                if not subagent_runner:
                    return ToolResult(
                        tool_name=invocation.tool_name,
                        status="tool_error",
                        error="Subagent runner is not available.",
                    )
                question = invocation.metadata.get("original_question", "")
                content = await subagent_runner(invocation.tool_name, question, invocation.pack_id)
            else:
                content = await self.mcp_manager.call_tool(invocation.tool_name, invocation.arguments)
            if not isinstance(content, str):
                content = str(content)
            return ToolResult(
                tool_name=invocation.tool_name,
                status="executed",
                content=content,
            )
        except Exception as exc:
            logger.error("[AgentOS] Tool execution failed: %s", exc)
            return ToolResult(
                tool_name=invocation.tool_name,
                status="tool_error",
                error=str(exc),
            )
