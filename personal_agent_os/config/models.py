from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    temperature: float = 0.95
    top_p: float = 1.0
    max_tokens: int = 768


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    provider: Literal["litellm"] = "litellm"
    active_model: str = "Model_2_DeepSeek"
    models: Dict[str, ModelProfile] = Field(default_factory=dict)


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_agent_id: str = "default_assistant"
    enable_cards: bool = True


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    level: str = "INFO"


class AgentOSConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
