from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .context import LogContextFilter
from .sanitization import sanitize_for_log


class SanitizingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        record.msg = sanitize_for_log(str(record.msg))
        record.args = tuple(sanitize_for_log(arg) for arg in record.args) if isinstance(record.args, tuple) else record.args
        try:
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


class ResilientFileHandler(logging.FileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
        super().emit(record)


def setup_logging(
    project_root: Path,
    log_dir: Optional[Path] = None,
    timestamp: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if log_dir is None:
        log_dir = project_root / "logs"

    session_log_dir = log_dir / timestamp
    session_log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("personal_agent_os")
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    context_filter = LogContextFilter()
    formatter = SanitizingFormatter(
        "%(asctime)s [%(levelname)s] [%(name)s] "
        "[trace=%(trace_id)s request=%(request_id)s tool=%(tool_call_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    module_logs = {
        "personal_agent_os": "app.log",
        "personal_agent_os.runtime": "runtime.log",
        "personal_agent_os.llm": "llm.log",
        "personal_agent_os.tools": "tools.log",
        "personal_agent_os.memory": "memory.log",
        "personal_agent_os.api": "api.log",
        "personal_agent_os.legacy": "legacy.log",
    }

    for logger_name, filename in module_logs.items():
        handler = ResilientFileHandler(session_log_dir / filename, encoding="utf-8", mode="a")
        handler.setLevel(file_level)
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        handler.addFilter(lambda record, prefix=logger_name: record.name == prefix or record.name.startswith(prefix + "."))
        root_logger.addHandler(handler)

    root_logger.info("Personal Agent OS logging initialized at %s", str(session_log_dir))
    return root_logger


def get_logger(name: str) -> logging.Logger:
    if name.startswith("personal_agent_os"):
        return logging.getLogger(name)
    return logging.getLogger(f"personal_agent_os.{name}")
