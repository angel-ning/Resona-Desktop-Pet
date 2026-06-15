from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..backend.skill_router import SkillRegistry
from ..config import ConfigManager

logger = logging.getLogger("AgentOS.Pack")


@dataclass(frozen=True)
class PersonaDefinition:
    pack_id: str
    name: str
    username_default: str
    tts_language: str
    prompts: List[Dict[str, str]] = field(default_factory=list)
    prompt_text: str = ""
    outfits: List[Dict[str, Any]] = field(default_factory=list)
    sovits_model: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    tags: List[str]
    allowed_tools: List[str]
    prompt_prefix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolPolicyDefinition:
    default_effect: str = "deny"
    payment_requires_confirmation: bool = True
    allowed_by_skill: Dict[str, List[str]] = field(default_factory=dict)
    denied_tools: List[str] = field(default_factory=list)
    confirmation_tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TriggerDefinition:
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    plugin_triggers: Dict[str, str] = field(default_factory=dict)
    plugin_actions: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedPack:
    pack_id: str
    folder_name: str
    metadata: Dict[str, Any]
    persona: PersonaDefinition
    skills: List[SkillDefinition]
    tool_policy: ToolPolicyDefinition
    triggers: TriggerDefinition
    assets: Dict[str, Any]
    config_overrides: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LegacyPackAdapter:
    """Projects existing Resona packs into the Agent OS pack model.

    This adapter is intentionally read-only: it lets the runtime consume today's
    packs as persona/assets/triggers without forcing pack authors to migrate yet.
    """

    def __init__(self, config: ConfigManager, skill_registry: Optional[SkillRegistry] = None):
        self.config = config
        self.pack_manager = config.pack_manager
        self.skill_registry = skill_registry or SkillRegistry()

    def load(self, pack_id: Optional[str] = None) -> NormalizedPack:
        folder_name = self._resolve_folder(pack_id)
        pack_data = self.pack_manager._get_pack_data(folder_name) or {}
        info = pack_data.get("pack_info", {})
        character = pack_data.get("character", {})
        logic = pack_data.get("logic", {})
        audio = pack_data.get("audio", {})
        agent_pack_id = info.get("id") or pack_data.get("id") or folder_name

        persona = PersonaDefinition(
            pack_id=agent_pack_id,
            name=character.get("name", "Unknown"),
            username_default=character.get("username_default", "User"),
            tts_language=character.get("tts_language", "ja"),
            prompts=list(logic.get("prompts", [])),
            prompt_text=self._read_prompt_text(folder_name),
            outfits=list(character.get("outfits", [])),
            sovits_model=dict(character.get("sovits_model", {})),
        )

        skills = self._load_default_skills()
        tool_policy = ToolPolicyDefinition(
            allowed_by_skill={skill.name: list(skill.allowed_tools) for skill in skills},
            denied_tools=[
                "exec_shell",
                "write_file",
                "edit_lines",
                "force_kill_task",
                "delete_file",
                "remove_file",
            ],
            confirmation_tools=[
                "payment",
                "checkout",
                "alipay",
                "wechat_pay",
                "place_order",
            ],
        )

        triggers = TriggerDefinition(
            triggers=self._load_triggers(folder_name),
            plugin_triggers=dict(getattr(self.pack_manager, "plugin_trigger_map", {})),
            plugin_actions=dict(getattr(self.pack_manager, "plugin_action_map", {})),
        )

        assets = {
            "audio": dict(audio),
            "outfits": list(character.get("outfits", [])),
            "logic_configs": dict(logic.get("interaction_configs", {})),
            "plugins": logic.get("plugins"),
        }

        return NormalizedPack(
            pack_id=agent_pack_id,
            folder_name=folder_name,
            metadata=dict(info),
            persona=persona,
            skills=skills,
            tool_policy=tool_policy,
            triggers=triggers,
            assets=assets,
            config_overrides=self._read_override_config(folder_name),
        )

    def _resolve_folder(self, pack_id: Optional[str]) -> str:
        requested = pack_id or self.pack_manager.active_pack_id
        self.pack_manager._scan_packs()
        return self.pack_manager.id_map.get(requested, requested)

    def _read_prompt_text(self, folder_name: str) -> str:
        try:
            return self.config.get_prompt(pack_id=folder_name)
        except Exception as exc:
            logger.warning("[AgentOS] Failed to read prompt for pack %s: %s", folder_name, exc)
            return ""

    def _load_default_skills(self) -> List[SkillDefinition]:
        raw_skills = getattr(self.skill_registry, "_skills", {})
        return [
            SkillDefinition(
                name=skill.name,
                description=skill.description,
                tags=list(skill.tags),
                allowed_tools=list(skill.allowed_tools),
                prompt_prefix=skill.prompt_prefix,
            )
            for skill in raw_skills.values()
        ]

    def _load_triggers(self, folder_name: str) -> List[Dict[str, Any]]:
        try:
            triggers = self.pack_manager.get_resolved_triggers(folder_name)
            return list(triggers or [])
        except Exception as exc:
            logger.warning("[AgentOS] Failed to load triggers for pack %s: %s", folder_name, exc)
            return []

    def _read_override_config(self, folder_name: str) -> Dict[str, Dict[str, str]]:
        override_path = self.pack_manager.packs_dir / folder_name / "override_config.cfg"
        if not override_path.exists():
            return {}

        import configparser

        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(override_path, encoding="utf-8")
        except Exception as exc:
            logger.warning("[AgentOS] Failed to read override config %s: %s", override_path, exc)
            return {}

        return {
            section: {key: value for key, value in parser.items(section)}
            for section in parser.sections()
        }
