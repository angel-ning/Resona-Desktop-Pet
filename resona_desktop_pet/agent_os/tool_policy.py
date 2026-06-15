from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional

from .contracts import ToolInvocation


@dataclass(frozen=True)
class ToolPolicyDecision:
    effect: str
    reason: str
    requires_confirmation: bool = False

    @property
    def allowed(self) -> bool:
        return self.effect == "allow"

    def to_dict(self):
        return asdict(self)


class ToolPolicy:
    """Runtime-side final gate for tool execution.

    Skill Router controls what the LLM sees. This class checks what the runtime
    will actually execute, so accidental exposure or malformed tool calls do not
    become authority.
    """

    def __init__(
        self,
        denied_patterns: Optional[Iterable[str]] = None,
        confirmation_patterns: Optional[Iterable[str]] = None,
    ):
        self.denied_patterns = list(denied_patterns or [
            "exec_shell",
            "write_file",
            "edit_lines",
            "delete_*",
            "remove_*",
            "force_kill_*",
            "taskkill*",
        ])
        self.confirmation_patterns = list(confirmation_patterns or [
            "*payment*",
            "*pay*",
            "*checkout*",
            "*place_order*",
            "*submit_order*",
            "*alipay*",
            "*wechat*",
        ])

    def evaluate(self, invocation: ToolInvocation) -> ToolPolicyDecision:
        tool_name = invocation.tool_name or ""
        allowed_tools = invocation.allowed_tools or []

        if not tool_name:
            return ToolPolicyDecision("deny", "Tool call is missing a name.")

        if allowed_tools and not self._matches_any(tool_name, allowed_tools):
            return ToolPolicyDecision(
                "deny",
                f"Tool '{tool_name}' is not visible for skill '{invocation.skill}'.",
            )

        if not allowed_tools:
            return ToolPolicyDecision(
                "deny",
                f"No runtime allow-list was provided for tool '{tool_name}'.",
            )

        if self._matches_any(tool_name, self.denied_patterns):
            return ToolPolicyDecision(
                "deny",
                f"Tool '{tool_name}' is blocked by runtime policy.",
            )

        if self._matches_any(tool_name, self.confirmation_patterns):
            return ToolPolicyDecision(
                "confirm",
                f"Tool '{tool_name}' requires user confirmation.",
                requires_confirmation=True,
            )

        return ToolPolicyDecision("allow", f"Tool '{tool_name}' allowed.")

    def _matches_any(self, tool_name: str, patterns: List[str]) -> bool:
        return any(fnmatch.fnmatchcase(tool_name, pattern) for pattern in patterns)
