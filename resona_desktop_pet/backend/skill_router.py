import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    tags: List[str]
    allowed_tools: List[str]
    prompt_prefix: Optional[str] = None


@dataclass(frozen=True)
class SkillRouteContext:
    source: str
    pack_id: Optional[str] = None
    history_summary: Optional[str] = None
    extra_context: Optional[str] = None
    ocr_context: Optional[str] = None


@dataclass(frozen=True)
class SkillRouteResult:
    skill: Skill
    reason: Dict[str, str] = field(default_factory=dict)


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {
            "safe_mode": Skill(
                name="safe_mode",
                description="Conservative fallback skill with memory recall and read-only file inspection.",
                tags=["default", "safe", "fallback"],
                allowed_tools=[
                    "memory_search",
                    "list_directory",
                    "read_file",
                    "count_lines",
                    "search_files",
                ],
                prompt_prefix=(
                    "[Skill: safe_mode]\n"
                    "Use only conservative read-only tools when helpful. Avoid destructive or write actions."
                ),
            ),
            "memory": Skill(
                name="memory",
                description="Long-term memory search and maintenance.",
                tags=["memory", "remember", "recall", "forget", "preference"],
                allowed_tools=[
                    "memory_search",
                    "memory_store",
                    "memory_update",
                    "memory_delete",
                ],
                prompt_prefix=(
                    "[Skill: memory]\n"
                    "Use memory tools only for explicit recall, storage, update, or deletion of memories."
                ),
            ),
            "timer": Skill(
                name="timer",
                description="Schedule future reminders or timed events.",
                tags=["timer", "reminder", "schedule", "alarm", "later"],
                allowed_tools=["schedule_timer_event"],
                prompt_prefix=(
                    "[Skill: timer]\n"
                    "Use timer tools only when the user asks to schedule a future reminder or event."
                ),
            ),
            "filesystem_read": Skill(
                name="filesystem_read",
                description="Read-only filesystem inspection and search.",
                tags=["file", "folder", "directory", "read", "search", "inspect"],
                allowed_tools=[
                    "list_directory",
                    "read_file",
                    "count_lines",
                    "search_files",
                ],
                prompt_prefix=(
                    "[Skill: filesystem_read]\n"
                    "Use read-only filesystem tools only. Do not write, edit, delete, or execute files."
                ),
            ),
        }

    def get(self, name: str) -> Skill:
        return self._skills[name]


class SkillRouter:
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or SkillRegistry()
        self._rules = [
            (
                "memory",
                [
                    "remember",
                    "memory",
                    "recall",
                    "forget",
                    "forgot",
                    "preference",
                    "what do you know about me",
                    "what do you remember",
                ],
            ),
            (
                "timer",
                [
                    "remind",
                    "reminder",
                    "timer",
                    "alarm",
                    "schedule",
                    "later",
                ],
            ),
            (
                "filesystem_read",
                [
                    "read file",
                    "open file",
                    "list directory",
                    "list folder",
                    "search files",
                    "count lines",
                    "inspect file",
                    "show file",
                ],
            ),
        ]

    def route(self, query: str, context: SkillRouteContext) -> SkillRouteResult:
        searchable = self._normalize(
            " ".join(
                part
                for part in [
                    query,
                    context.extra_context or "",
                    context.ocr_context or "",
                    context.history_summary or "",
                ]
                if part
            )
        )

        for skill_name, keywords in self._rules:
            for keyword in keywords:
                normalized_keyword = self._normalize(keyword)
                if normalized_keyword and normalized_keyword in searchable:
                    return SkillRouteResult(
                        skill=self.registry.get(skill_name),
                        reason={
                            "matched_skill": skill_name,
                            "matched_rule": normalized_keyword,
                            "confidence": "rule-based",
                        },
                    )

        return SkillRouteResult(
            skill=self.registry.get("safe_mode"),
            reason={
                "matched_skill": "safe_mode",
                "matched_rule": "fallback",
                "confidence": "rule-based",
            },
        )

    def _normalize(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return text.strip()
