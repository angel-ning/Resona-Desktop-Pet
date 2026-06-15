from __future__ import annotations

import logging
from typing import Callable, List, Optional

from ..backend.llm_backend import ConversationHistory, LLMResponse
from ..backend.skill_router import SkillRouteContext, SkillRouter
from ..config import ConfigManager
from .contracts import AgentEvent, AgentIntent, AgentRequest
from .pack_adapter import LegacyPackAdapter, NormalizedPack
from .tool_executor import ToolExecutionService
from .tool_providers import ToolProviderRegistry

logger = logging.getLogger("AgentOS.Runtime")

EventSink = Callable[[AgentEvent], None]


class AgentRuntime:
    """Compatibility facade for the Personal Agent OS runtime.

    In this first migration slice, the runtime owns pack normalization, skill
    intent creation, provider metadata, and the deterministic tool executor.
    It still delegates final conversational generation to the existing
    LLMBackend so PySide6, FastAPI, MCP, and memory remain compatible.
    """

    def __init__(
        self,
        config: ConfigManager,
        llm_backend,
        mcp_manager=None,
        event_sink: Optional[EventSink] = None,
    ):
        self.config = config
        self.llm_backend = llm_backend
        self.mcp_manager = mcp_manager
        self.event_sink = event_sink
        self.skill_router = SkillRouter()
        self.pack_adapter = LegacyPackAdapter(config)
        self.tool_executor = ToolExecutionService(mcp_manager)
        self.provider_registry = ToolProviderRegistry()

        if hasattr(self.llm_backend, "set_tool_executor"):
            self.llm_backend.set_tool_executor(self.tool_executor)

    def load_pack(self, pack_id: Optional[str] = None) -> NormalizedPack:
        return self.pack_adapter.load(pack_id)

    def list_tool_providers(self) -> List[dict]:
        return self.provider_registry.list_specs()

    def create_intent(
        self,
        request: AgentRequest,
        history_summary: Optional[str] = None,
        extra_context: Optional[str] = None,
        ocr_context: Optional[str] = None,
    ) -> AgentIntent:
        route = self.skill_router.route(
            request.user_text,
            SkillRouteContext(
                source=request.source,
                pack_id=request.pack_id,
                history_summary=history_summary,
                extra_context=extra_context,
                ocr_context=ocr_context,
            ),
        )
        return AgentIntent(
            kind="chat_or_task",
            user_text=request.user_text,
            skill=route.skill.name,
            capability=route.skill.description,
            parameters={
                "allowed_tools": list(route.skill.allowed_tools),
                "route_reason": dict(route.reason),
            },
            needs_tools=bool(route.skill.allowed_tools),
            request_id=request.request_id,
        )

    async def query_text(
        self,
        text: str,
        history: Optional[ConversationHistory] = None,
        extra_context: Optional[str] = None,
        pack_id: Optional[str] = None,
        source: str = "desktop",
        session_id: Optional[str] = None,
    ) -> LLMResponse:
        request = AgentRequest(
            user_text=text,
            source=source,
            session_id=session_id,
            pack_id=pack_id,
            context={"extra_context": extra_context} if extra_context else {},
        )
        self._emit("request_received", request.request_id, request.to_dict())
        intent = self.create_intent(request, extra_context=extra_context)
        self._emit("intent_created", request.request_id, intent.to_dict())

        response = await self.llm_backend.query(
            text,
            history=history,
            extra_context=extra_context,
            pack_id=pack_id,
            source=source,
            session_id=session_id,
        )
        self._emit(
            "response_ready",
            request.request_id,
            {
                "error": response.error,
                "emotion": response.emotion,
                "text_display": response.text_display,
            },
        )
        return response

    async def query_idle(self, text: str, pack_id: Optional[str] = None) -> LLMResponse:
        request = AgentRequest(
            user_text=text,
            source="idle_trigger",
            pack_id=pack_id,
        )
        self._emit("request_received", request.request_id, request.to_dict())
        response = await self.llm_backend.query_idle(text, pack_id=pack_id)
        self._emit(
            "response_ready",
            request.request_id,
            {
                "error": response.error,
                "emotion": response.emotion,
                "text_display": response.text_display,
            },
        )
        return response

    def _emit(self, event_type: str, request_id: Optional[str], payload: dict) -> None:
        event = AgentEvent(type=event_type, request_id=request_id, payload=payload)
        logger.info("[AgentOS] Event: %s", event.to_dict())
        if self.event_sink:
            try:
                self.event_sink(event)
            except Exception as exc:
                logger.warning("[AgentOS] Event sink failed: %s", exc)
