from __future__ import annotations

import json
import re
from pathlib import PureWindowsPath
from typing import Any

_API_KEY_RE = re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*([A-Za-z0-9_\-\.]{12,})")
_RAW_SECRET_RE = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|[A-Za-z0-9_\-]*secret[A-Za-z0-9_\-]*secret[A-Za-z0-9_\-]*)\b", re.IGNORECASE)
_BASE64_IMAGE_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]{80,}")
_IP_CONTEXT_RE = re.compile(r"\[User IP:.*?\]", re.DOTALL)
_WINDOWS_ABS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*")
_LONG_TEXT_LIMIT = 2000


def _mask_string(value: str) -> str:
    value = _API_KEY_RE.sub(lambda m: f"{m.group(1)}: [REDACTED]", value)
    value = _RAW_SECRET_RE.sub("[REDACTED_SECRET]", value)
    value = _BASE64_IMAGE_RE.sub("[BASE64_IMAGE_REDACTED]", value)
    value = _IP_CONTEXT_RE.sub("[User IP: REDACTED]", value)

    def mask_path(match: re.Match) -> str:
        raw_path = match.group(0)
        name = PureWindowsPath(raw_path).name
        return f"[ABS_PATH_REDACTED]\\{name}" if name else "[ABS_PATH_REDACTED]"

    value = _WINDOWS_ABS_PATH_RE.sub(mask_path, value)
    if len(value) > _LONG_TEXT_LIMIT:
        value = value[:_LONG_TEXT_LIMIT] + "... [TRUNCATED]"
    return value


def sanitize_for_log(value: Any) -> Any:
    if isinstance(value, str):
        return _mask_string(value)
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            lower_key = str(key).lower()
            if lower_key in {"api_key", "apikey", "authorization", "secret", "token"}:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value]
    return value


def dumps_sanitized(value: Any) -> str:
    return json.dumps(sanitize_for_log(value), ensure_ascii=False, default=str)
