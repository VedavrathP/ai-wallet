"""Retry logic with exponential backoff for network errors."""

import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {502, 503, 504}

# Retryable exceptions
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)

T = TypeVar("T")


def calculate_backoff(
    attempt: int,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff delay with optional jitter.

    Args:
        attempt: The current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2**attempt), max_delay)
    if jitter:
        delay = delay * (0.5 + random.random())
    return delay


def with_retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = calculate_backoff(attempt, base_delay, max_delay)
                        time.sleep(delay)
                    continue
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in RETRYABLE_STATUS_CODES:
                        last_exception = e
                        if attempt < max_retries:
                            delay = calculate_backoff(attempt, base_delay, max_delay)
                            time.sleep(delay)
                        continue
                    raise

            # If we've exhausted all retries, raise the last exception
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


class RetryableClient:
    """Mixin class providing retry-enabled HTTP methods."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def _should_retry(self, exception: Exception) -> bool:
        """Check if the exception is retryable."""
        if isinstance(exception, RETRYABLE_EXCEPTIONS):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code in RETRYABLE_STATUS_CODES
        return False

    def _execute_with_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function with retry logic."""
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if self._should_retry(e):
                    last_exception = e
                    if attempt < self.max_retries:
                        delay = calculate_backoff(
                            attempt, self.base_delay, self.max_delay
                        )
                        time.sleep(delay)
                    continue
                raise

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Unexpected state in retry logic")
