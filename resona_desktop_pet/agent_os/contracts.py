from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class AgentRequest:
    user_text: str
    source: str = "desktop"
    session_id: Optional[str] = None
    pack_id: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: _new_id("req"))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentIntent:
    kind: str
    user_text: str
    skill: str
    capability: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    missing_information: List[str] = field(default_factory=list)
    needs_tools: bool = False
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolInvocation:
    tool_name: str
    arguments: Dict[str, Any]
    skill: str
    source: str
    pack_id: Optional[str] = None
    request_id: Optional[str] = None
    allowed_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    status: str
    content: str = ""
    error: Optional[str] = None
    policy_reason: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "executed"

    def to_tool_message(self) -> str:
        if self.ok:
            return self.content
        if self.requires_confirmation:
            return f"Tool requires user confirmation: {self.policy_reason or self.tool_name}"
        if self.error:
            return f"Tool error: {self.error}"
        return f"Tool blocked by policy: {self.policy_reason or self.tool_name}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentEvent:
    type: str
    request_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResponse:
    request_id: str
    text_display: str = ""
    text_tts: str = ""
    emotion: str = "<E:smile>"
    events: List[AgentEvent] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    raw_response: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
