from __future__ import annotations

from typing import Optional

from personal_agent_os.config import AgentOSConfig, ConfigView
from personal_agent_os.domain import ToolManifest
from personal_agent_os.llm import LLMConfig, LiteLLMClient
from personal_agent_os.runtime import AgentRuntime
from personal_agent_os.tools import FunctionToolProvider, ToolRouter

PROFILE_MODEL_PREFIXES = {
    "Model_1_OpenAI": "openai",
    "Model_2_DeepSeek": "deepseek",
    "Model_3_Claude": "anthropic",
    "Model_4_Kimi": "moonshot",
    "Model_5_Gemini": "gemini",
    "Model_6_Grok": "xai",
    "Model_7_Qwen": "openai",
    "Model_8_GitHub": "openai",
    "Model_9_OpenAI_Compatible": "openai",
    "Model_10_Zhipu": "openai",
    "Model_Local": "openai",
}


def create_runtime(config: Optional[AgentOSConfig | ConfigView] = None) -> AgentRuntime:
    effective_config = config.effective if isinstance(config, ConfigView) else config
    provider = FunctionToolProvider()
    provider.register(
        ToolManifest(
            name="demo_write_file",
            description="Demo filesystem write tool used to verify capability guarding.",
            required_capabilities=["allow_fs_write"],
            provider="function",
        ),
        lambda path, content: {"path": path, "bytes": len(content)},
    )
    provider.register(
        ToolManifest(
            name="demo_card",
            description="Demo card producer.",
            required_capabilities=["allow_cards"],
            provider="function",
        ),
        lambda title="Demo", body="Card": {"title": title, "body": body},
    )
    llm_config = create_llm_config(effective_config)
    llm_client = LiteLLMClient() if llm_config else None
    return AgentRuntime(tool_router=ToolRouter(providers=[provider]), llm_client=llm_client, llm_config=llm_config)


def create_llm_config(config: Optional[AgentOSConfig]) -> Optional[LLMConfig]:
    if not config:
        return None
    settings = config.llm
    active_model = settings.active_model
    profile = settings.models.get(active_model)
    if not settings.enabled or not profile or not profile.model_name.strip():
        return None
    return LLMConfig(
        model=normalize_litellm_model(active_model, profile.model_name),
        api_key=profile.api_key or None,
        base_url=profile.base_url or None,
        temperature=profile.temperature,
        top_p=profile.top_p,
        max_tokens=profile.max_tokens,
    )


def normalize_litellm_model(profile_id: str, model_name: str) -> str:
    model = model_name.strip()
    if "/" in model:
        return model
    prefix = PROFILE_MODEL_PREFIXES.get(profile_id)
    return f"{prefix}/{model}" if prefix else model
