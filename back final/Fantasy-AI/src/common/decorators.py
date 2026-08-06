"""Reusable function decorators shared across the codebase.

Keeping cross-cutting behavior (retrying, timing) as decorators avoids
duplicating boilerplate in every data-source implementation, service,
or pipeline step.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from src.config.logging_config import get_logger

logger = get_logger(__name__)

_T = TypeVar("_T")


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Retry a function call on failure with a fixed delay.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        delay_seconds: Seconds to wait between attempts.
        exceptions: Tuple of exception types that should trigger a
            retry. Any other exception propagates immediately.

    Returns:
        Callable: A decorator that wraps the target function with
        retry logic.
    """

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> _T:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # type: ignore[misc]
                    last_exception = exc
                    logger.warning(
                        "Attempt %d/%d for %s failed: %s",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        exc,
                    )
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


def timed(func: Callable[..., _T]) -> Callable[..., _T]:
    """Log the execution time of the wrapped function.

    Args:
        func: Function to time.

    Returns:
        Callable: The wrapped function, logging its duration on return.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> _T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("%s completed in %.3fs", func.__qualname__, elapsed)
        return result

    return wrapper
