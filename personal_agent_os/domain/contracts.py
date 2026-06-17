from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ClientCapabilities(BaseModel):
    allow_fs_read: bool = False
    allow_fs_write: bool = False
    allow_shell: bool = False
    allow_desktop_control: bool = False
    allow_audio_output: bool = True
    allow_cards: bool = True
    allow_network: bool = False


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: str = "default_assistant"
    context: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    client_capabilities: ClientCapabilities = Field(default_factory=ClientCapabilities)
    request_id: str = Field(default_factory=lambda: str(uuid4()))


class Card(BaseModel):
    type: str
    title: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class PermissionBlocked(BaseModel):
    code: Literal["permission_blocked"] = "permission_blocked"
    reason: str
    missing_capabilities: List[str] = Field(default_factory=list)
    alternative_actions: List[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False


class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str = Field(default_factory=lambda: str(uuid4()))


class ToolResult(BaseModel):
    ok: bool
    name: str
    content: Any = None
    tool_call_id: Optional[str] = None
    blocked: Optional[PermissionBlocked] = None
    error: Optional[str] = None


class ToolManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    required_capabilities: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict, alias="schema")
    provider: str = "function"


class SkillManifest(BaseModel):
    id: str
    name: str
    description: str = ""
    triggers: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    workflow: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    enabled: bool = True


class AgentEvent(BaseModel):
    type: Literal["thinking", "tool_call", "card", "message", "audio", "error", "done"]
    trace_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentResponse(BaseModel):
    trace_id: str
    request_id: str
    conversation_id: Optional[str] = None
    message: str = ""
    cards: List[Card] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = Field(default_factory=list)
    audio: Optional[Dict[str, Any]] = None
    tool_results: List[ToolResult] = Field(default_factory=list)
    requires_user_input: bool = False
    error: Optional[str] = None
