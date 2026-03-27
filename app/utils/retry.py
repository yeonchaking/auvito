"""Retry utilities with exponential backoff."""

import asyncio
import random
from typing import TypeVar, Callable, Awaitable

from app.domain.enums import FailureClass

T = TypeVar("T")


async def retry_async(
    func: Callable[..., Awaitable[T]],
    max_attempts: int = 3,
    backoff_base_s: float = 2,
    jitter: bool = True,
    failure_class_predicate=None,
) -> T:
    """Retry an async function with exponential backoff."""
    last_error = None

    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            last_error = e

            # Check if we should retry based on failure class
            if failure_class_predicate and not failure_class_predicate(e):
                raise

            if attempt < max_attempts - 1:
                wait_seconds = backoff_base_s ** (attempt + 1)
                if jitter:
                    wait_seconds += random.uniform(0, 1)
                await asyncio.sleep(wait_seconds)

    raise last_error


def is_retryable_failure(failure_class: FailureClass) -> bool:
    """Check if a failure class is retryable."""
    retryable = {
        FailureClass.TRANSIENT_PROVIDER,
        FailureClass.LOCAL_TOOL_TRANSIENT,
        FailureClass.ASYNC_JOB_TIMEOUT,
    }
    return failure_class in retryable
