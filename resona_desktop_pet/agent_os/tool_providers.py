from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ToolProviderSpec:
    name: str
    priority: int
    description: str
    available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "priority": self.priority,
            "description": self.description,
            "available": self.available,
        }


class ToolProviderRegistry:
    """Documents the Agent OS provider order before all providers are wired.

    MCP is active today. Playwright, Browser-Use, and OpenClaw are explicit
    provider slots so future work adds adapters without changing runtime
    request/response contracts.
    """

    def __init__(self):
        self._providers = [
            ToolProviderSpec(
                name="mcp",
                priority=10,
                description="Existing MCP tool manager and memory tools.",
                available=True,
            ),
            ToolProviderSpec(
                name="playwright",
                priority=20,
                description="Deterministic scripts for high-frequency H5 flows.",
                available=False,
            ),
            ToolProviderSpec(
                name="browser_use",
                priority=30,
                description="LLM-assisted semantic browser navigation.",
                available=False,
            ),
            ToolProviderSpec(
                name="openclaw",
                priority=90,
                description="Desktop-level computer-use fallback.",
                available=False,
            ),
        ]

    def list_specs(self) -> List[Dict[str, Any]]:
        return [provider.to_dict() for provider in self._providers]
