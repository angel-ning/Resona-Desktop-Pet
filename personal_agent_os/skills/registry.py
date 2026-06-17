from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from personal_agent_os.domain import SkillManifest
from personal_agent_os.infrastructure.logging import get_logger

logger = get_logger("runtime.skills")


class SkillRegistry:
    def __init__(self, manifests: Optional[List[SkillManifest]] = None):
        self._manifests: Dict[str, SkillManifest] = {manifest.id: manifest for manifest in manifests or []}

    @classmethod
    def from_prompts(cls, prompts_root: Path) -> "SkillRegistry":
        manifests: List[SkillManifest] = []
        for manifest_path in (prompts_root / "agents").glob("*/manifest.*"):
            manifest = cls._load_manifest(manifest_path)
            if manifest:
                manifests.append(manifest)
        for prompt_path in (prompts_root / "skills").glob("*.md"):
            skill_id = prompt_path.stem
            manifests.append(SkillManifest(id=skill_id, name=skill_id.replace("_", " ").title(), enabled=True))
        registry = cls(manifests)
        logger.info("Loaded %d skill/agent manifests", len(registry.list()))
        return registry

    @staticmethod
    def _load_manifest(path: Path) -> Optional[SkillManifest]:
        try:
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                import yaml

                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return SkillManifest(**data)
        except Exception as exc:
            logger.warning("Failed to load manifest %s: %s", str(path), exc)
            return None

    def register(self, manifest: SkillManifest) -> None:
        self._manifests[manifest.id] = manifest

    def get(self, skill_id: str) -> Optional[SkillManifest]:
        return self._manifests.get(skill_id)

    def list(self) -> List[SkillManifest]:
        return list(self._manifests.values())

    def reload(self, prompts_root: Path) -> List[SkillManifest]:
        refreshed = self.from_prompts(prompts_root)
        self._manifests = {manifest.id: manifest for manifest in refreshed.list()}
        return self.list()
