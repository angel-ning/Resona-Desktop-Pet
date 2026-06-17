from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import yaml

from personal_agent_os.infrastructure.logging import get_logger

from .models import AgentOSConfig

logger = get_logger("config")

SENSITIVE_KEYS = ("api_key", "secret", "token", "password")
ALLOWED_EXACT_PATCH_FIELDS = {
    "llm.enabled",
    "llm.provider",
    "llm.active_model",
    "runtime.default_agent_id",
    "runtime.enable_cards",
    "logging.level",
}
ALLOWED_MODEL_PATCH_FIELDS = {"api_key", "base_url", "model_name", "temperature", "top_p", "max_tokens"}
PROFILE_ENV_OVERRIDES = {
    "AGENT_OS_MODEL": "model_name",
    "AGENT_OS_API_KEY": "api_key",
    "AGENT_OS_BASE_URL": "base_url",
    "AGENT_OS_TEMPERATURE": "temperature",
    "AGENT_OS_TOP_P": "top_p",
    "AGENT_OS_MAX_TOKENS": "max_tokens",
}


@dataclass(frozen=True)
class ConfigView:
    persisted: AgentOSConfig
    effective: AgentOSConfig
    env_overrides: List[str]

    def to_safe_dict(self) -> Dict[str, Any]:
        return {
            "persisted": mask_sensitive(self.persisted.model_dump()),
            "effective": mask_sensitive(self.effective.model_dump()),
            "env_overrides": list(self.env_overrides),
        }


class ConfigManager:
    def __init__(
        self,
        project_root: Optional[Path] = None,
        defaults_path: Optional[Path] = None,
        user_config_path: Optional[Path] = None,
    ):
        self.project_root = (project_root or Path.cwd()).resolve()
        self.defaults_path = defaults_path or Path(__file__).resolve().parent / "defaults.yaml"
        self.user_config_path = user_config_path or self.project_root / "config" / "agent_os.yaml"

    def load(self) -> ConfigView:
        defaults_data = self._read_yaml(self.defaults_path)
        user_data = self._read_yaml(self.user_config_path)
        persisted_data = shallow_section_merge(defaults_data, user_data)
        persisted = AgentOSConfig.model_validate(persisted_data)

        effective_data = copy.deepcopy(persisted.model_dump())
        env_overrides = self._apply_env_overrides(effective_data)
        effective = AgentOSConfig.model_validate(effective_data)
        logger.info("Loaded Agent OS config path=%s env_overrides=%s", str(self.user_config_path), env_overrides)
        return ConfigView(persisted=persisted, effective=effective, env_overrides=env_overrides)

    def save_patch(self, patch: Mapping[str, Any]) -> ConfigView:
        flat_patch = flatten_patch(patch)
        disallowed = sorted(field for field in flat_patch if not is_allowed_patch_field(field))
        if disallowed:
            raise ValueError(f"Unsupported config fields: {', '.join(disallowed)}")

        current = self._read_yaml(self.user_config_path)
        updated = shallow_section_merge(current, patch)
        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_config_path.write_text(yaml.safe_dump(updated, sort_keys=False, allow_unicode=True), encoding="utf-8")
        logger.info("Saved Agent OS config patch fields=%s path=%s", sorted(flat_patch), str(self.user_config_path))
        return self.load()

    def get_effective_config(self, section: str, key: str, fallback: Any = None) -> tuple[Any, str]:
        view = self.load()
        persisted_value = getattr(getattr(view.persisted, section, None), key, fallback)
        effective_value = getattr(getattr(view.effective, section, None), key, fallback)
        source = "env" if f"{section}.{key}" in view.env_overrides else "local"
        if persisted_value == fallback and effective_value == fallback:
            source = "fallback"
        return effective_value, source

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> List[str]:
        overrides: List[str] = []
        llm_data = config_data.setdefault("llm", {})
        active_override = os.getenv("AGENT_OS_ACTIVE_MODEL")
        if active_override:
            llm_data["active_model"] = active_override
            overrides.append("llm.active_model")

        active_model = str(llm_data.get("active_model") or "Model_2_DeepSeek")
        profiles = llm_data.setdefault("models", {})
        active_profile = profiles.setdefault(active_model, {})
        for env_name, key in PROFILE_ENV_OVERRIDES.items():
            raw = os.getenv(env_name)
            if raw is None:
                continue
            value: Any = raw
            if key in {"temperature", "top_p"}:
                try:
                    value = float(raw)
                except ValueError:
                    continue
            elif key == "max_tokens":
                try:
                    value = int(raw)
                except ValueError:
                    continue
            active_profile[key] = value
            overrides.append(f"llm.models.{active_model}.{key}")
        return overrides


def shallow_section_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(dict(base or {}))
    for section, value in (override or {}).items():
        if isinstance(value, Mapping) and isinstance(result.get(section), Mapping):
            result[section] = shallow_section_merge(result[section], value)
        else:
            result[section] = copy.deepcopy(value)
    return result


def is_allowed_patch_field(field: str) -> bool:
    if field in ALLOWED_EXACT_PATCH_FIELDS:
        return True
    parts = field.split(".")
    return (
        len(parts) == 4
        and parts[0] == "llm"
        and parts[1] == "models"
        and bool(parts[2])
        and parts[3] in ALLOWED_MODEL_PATCH_FIELDS
    )


def flatten_patch(patch: Mapping[str, Any], prefix: str = "") -> List[str]:
    fields: List[str] = []
    for key, value in patch.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            fields.extend(flatten_patch(value, path))
        else:
            fields.append(path)
    return fields


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        masked = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in SENSITIVE_KEYS):
                masked[key] = "********" if item else ""
            else:
                masked[key] = mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value
