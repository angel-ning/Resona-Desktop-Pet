from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket

from personal_agent_os.application.factory import create_runtime
from personal_agent_os.config import ConfigManager
from personal_agent_os.domain import ChatRequest
from personal_agent_os.infrastructure.logging import get_logger, setup_logging
from personal_agent_os.runtime import AgentRuntime

logger = get_logger("api")


def create_app(
    runtime: Optional[AgentRuntime] = None,
    project_root: Optional[Path] = None,
    configure_logging: bool = False,
) -> FastAPI:
    resolved_project_root = project_root or Path.cwd()
    if configure_logging:
        setup_logging(resolved_project_root)

    app = FastAPI(title="Personal Agent OS", version="0.1.0")
    app.state.config_manager = ConfigManager(project_root=resolved_project_root)
    app.state.config_view = app.state.config_manager.load()
    app.state.runtime = runtime or create_runtime(app.state.config_view)

    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        logger.info("POST /api/chat")
        return await app.state.runtime.run(request)

    @app.websocket("/api/chat/stream")
    async def chat_stream(websocket: WebSocket):
        await websocket.accept()
        payload = await websocket.receive_json()
        request = ChatRequest(**payload)
        logger.info("WS /api/chat/stream")
        async for event in app.state.runtime.stream(request):
            await websocket.send_text(event.model_dump_json())

    @app.get("/api/skills")
    async def list_skills():
        return {"skills": [manifest.model_dump() for manifest in app.state.runtime.skill_registry.list()]}

    @app.post("/api/skills/reload")
    async def reload_skills():
        manifests = app.state.runtime.skill_registry.reload(app.state.runtime.prompt_loader.prompts_root)
        return {"skills": [manifest.model_dump() for manifest in manifests]}

    @app.get("/api/config")
    async def get_config():
        app.state.config_view = app.state.config_manager.load()
        return app.state.config_view.to_safe_dict()

    @app.patch("/api/config")
    async def patch_config(patch: dict):
        try:
            app.state.config_view = app.state.config_manager.save_patch(patch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Runtime is stateless orchestration only; existing short HTTP requests keep
        # their old runtime object, and new requests receive this replacement.
        app.state.runtime = create_runtime(app.state.config_view)
        return app.state.config_view.to_safe_dict()

    return app
