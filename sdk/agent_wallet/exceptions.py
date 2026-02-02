"""Exception classes for the Agent Wallet SDK."""

from typing import Any, Optional


class WalletAPIError(Exception):
    """Base exception for all Agent Wallet API errors."""

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.error_code or 'ERROR'}: {self.message}"


class InsufficientFunds(WalletAPIError):
    """Raised when the wallet has insufficient funds for the operation."""

    def __init__(
        self,
        message: str = "Insufficient funds",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="INSUFFICIENT_FUNDS",
            details=details,
        )


class ForbiddenScope(WalletAPIError):
    """Raised when the API key lacks the required scope for the operation."""

    def __init__(
        self,
        message: str = "Forbidden: insufficient scope",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN_SCOPE",
            details=details,
        )


class LimitExceeded(WalletAPIError):
    """Raised when a transaction or daily limit is exceeded."""

    def __init__(
        self,
        message: str = "Limit exceeded",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="LIMIT_EXCEEDED",
            details=details,
        )


class RecipientNotFound(WalletAPIError):
    """Raised when the specified recipient cannot be resolved."""

    def __init__(
        self,
        message: str = "Recipient not found",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=404,
            error_code="RECIPIENT_NOT_FOUND",
            details=details,
        )


class CurrencyMismatch(WalletAPIError):
    """Raised when currencies don't match between wallets."""

    def __init__(
        self,
        message: str = "Currency mismatch",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="CURRENCY_MISMATCH",
            details=details,
        )


class ConflictIdempotency(WalletAPIError):
    """Raised when an idempotency key conflict is detected."""

    def __init__(
        self,
        message: str = "Idempotency key conflict",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_code="IDEMPOTENCY_CONFLICT",
            details=details,
        )


class RateLimitExceeded(WalletAPIError):
    """Raised when the rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
        )


class WalletFrozen(WalletAPIError):
    """Raised when attempting to operate on a frozen wallet."""

    def __init__(
        self,
        message: str = "Wallet is frozen",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_code="WALLET_FROZEN",
            details=details,
        )


class HoldExpired(WalletAPIError):
    """Raised when attempting to capture or release an expired hold."""

    def __init__(
        self,
        message: str = "Hold has expired",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="HOLD_EXPIRED",
            details=details,
        )


class PaymentIntentExpired(WalletAPIError):
    """Raised when attempting to pay an expired payment intent."""

    def __init__(
        self,
        message: str = "Payment intent has expired",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="PAYMENT_INTENT_EXPIRED",
            details=details,
        )


# Mapping from error codes to exception classes
ERROR_CODE_MAP: dict[str, type[WalletAPIError]] = {
    "INSUFFICIENT_FUNDS": InsufficientFunds,
    "FORBIDDEN_SCOPE": ForbiddenScope,
    "LIMIT_EXCEEDED": LimitExceeded,
    "RECIPIENT_NOT_FOUND": RecipientNotFound,
    "CURRENCY_MISMATCH": CurrencyMismatch,
    "IDEMPOTENCY_CONFLICT": ConflictIdempotency,
    "RATE_LIMIT_EXCEEDED": RateLimitExceeded,
    "WALLET_FROZEN": WalletFrozen,
    "HOLD_EXPIRED": HoldExpired,
    "PAYMENT_INTENT_EXPIRED": PaymentIntentExpired,
}


def raise_for_error_response(
    status_code: int,
    response_data: dict[str, Any],
) -> None:
    """Raise the appropriate exception based on the API error response."""
    error_code = response_data.get("error_code", "")
    message = response_data.get("message", "Unknown error")
    details = response_data.get("details", {})

    # Try to find a specific exception class
    exception_class = ERROR_CODE_MAP.get(error_code, WalletAPIError)

    if exception_class == WalletAPIError:
        raise WalletAPIError(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )
    else:
        raise exception_class(message=message, details=details)
