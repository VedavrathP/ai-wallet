"""Rate limiting middleware."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict
from uuid import UUID

from fastapi import HTTPException, Request, status

from agent_wallet_service.core.config import settings


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)
    max_tokens: float = 100.0
    refill_rate: float = 100.0 / 60.0  # tokens per second (100 per minute)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket.

        Returns True if tokens were consumed, False if rate limit exceeded.
        """
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate time until the requested tokens will be available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate


class RateLimiter:
    """In-memory rate limiter using token bucket algorithm.

    This is a simple implementation suitable for development.
    For production, consider using Redis-based rate limiting.
    """

    def __init__(self, rpm: int = settings.RATE_LIMIT_RPM):
        """Initialize the rate limiter.

        Args:
            rpm: Requests per minute limit
        """
        self.rpm = rpm
        self.buckets: Dict[UUID, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(
                tokens=float(rpm),
                max_tokens=float(rpm),
                refill_rate=float(rpm) / 60.0,
            )
        )

    def check(self, api_key_id: UUID) -> None:
        """Check if the request is within rate limits.

        Raises HTTPException if rate limit is exceeded.
        """
        bucket = self.buckets[api_key_id]

        if not bucket.consume():
            retry_after = bucket.time_until_available()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded",
                    "details": {
                        "retry_after_seconds": round(retry_after, 2),
                        "limit_rpm": self.rpm,
                    },
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    def reset(self, api_key_id: UUID) -> None:
        """Reset the rate limit bucket for an API key."""
        if api_key_id in self.buckets:
            del self.buckets[api_key_id]


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request, api_key_id: UUID) -> None:
    """Check rate limit for the current request.

    This function should be called after authentication.
    """
    rate_limiter.check(api_key_id)
