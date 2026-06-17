from __future__ import annotations

from contextvars import ContextVar
from typing import Dict, Optional

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_tool_call_id: ContextVar[str] = ContextVar("tool_call_id", default="-")


def bind_log_context(
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
) -> Dict[str, object]:
    tokens: Dict[str, object] = {}
    if trace_id is not None:
        tokens["trace_id"] = _trace_id.set(trace_id)
    if request_id is not None:
        tokens["request_id"] = _request_id.set(request_id)
    if tool_call_id is not None:
        tokens["tool_call_id"] = _tool_call_id.set(tool_call_id)
    return tokens


def clear_log_context(tokens: Dict[str, object]) -> None:
    if "tool_call_id" in tokens:
        _tool_call_id.reset(tokens["tool_call_id"])
    if "request_id" in tokens:
        _request_id.reset(tokens["request_id"])
    if "trace_id" in tokens:
        _trace_id.reset(tokens["trace_id"])


def get_trace_id() -> str:
    return _trace_id.get()


class LogContextFilter:
    def filter(self, record) -> bool:
        record.trace_id = _trace_id.get()
        record.request_id = _request_id.get()
        record.tool_call_id = _tool_call_id.get()
        return True
