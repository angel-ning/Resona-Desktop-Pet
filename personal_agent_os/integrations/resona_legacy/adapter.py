from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from personal_agent_os.infrastructure.logging import get_logger

T = TypeVar("T")
logger = get_logger("legacy")


class ResonaLegacyAdapter:
    """Thread-pool boundary for all calls into legacy Resona code."""

    def __init__(
        self,
        legacy_root: Optional[Path] = None,
        timeout_seconds: float = 30.0,
        executor: Optional[Executor] = None,
    ):
        self.legacy_root = legacy_root
        self.timeout_seconds = timeout_seconds
        self.executor = executor

    async def run_blocking(
        self,
        func: Callable[..., T],
        *args: Any,
        timeout_seconds: Optional[float] = None,
        operation_name: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        loop = asyncio.get_running_loop()
        bound = partial(func, *args, **kwargs)
        operation = operation_name or getattr(func, "__name__", "legacy_operation")
        logger.debug("Legacy operation scheduled: %s", operation)
        try:
            future = loop.run_in_executor(self.executor, bound)
            result = await asyncio.wait_for(future, timeout=timeout_seconds or self.timeout_seconds)
            logger.debug("Legacy operation completed: %s", operation)
            return result
        except asyncio.TimeoutError:
            logger.error("Legacy operation timed out: %s", operation)
            raise TimeoutError(f"Legacy operation timed out: {operation}")
        except asyncio.CancelledError:
            logger.warning("Legacy operation cancelled: %s", operation)
            raise
        except Exception as exc:
            logger.exception("Legacy operation failed: %s", operation)
            raise RuntimeError(f"Legacy operation failed: {operation}: {exc}") from exc
