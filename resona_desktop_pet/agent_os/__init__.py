from .contracts import (
    AgentEvent,
    AgentIntent,
    AgentRequest,
    AgentResponse,
    ToolInvocation,
    ToolResult,
)

__all__ = [
    "AgentEvent",
    "AgentIntent",
    "AgentRequest",
    "AgentResponse",
    "AgentRuntime",
    "ToolExecutionService",
    "ToolInvocation",
    "ToolResult",
]


def __getattr__(name):
    if name == "AgentRuntime":
        from .runtime import AgentRuntime

        return AgentRuntime
    if name == "ToolExecutionService":
        from .tool_executor import ToolExecutionService

        return ToolExecutionService
    raise AttributeError(name)
