"""Tests for exception handling and HTTP status mapping."""

import pytest

from agent_wallet.exceptions import (
    ConflictIdempotency,
    CurrencyMismatch,
    ForbiddenScope,
    InsufficientFunds,
    LimitExceeded,
    RecipientNotFound,
    WalletAPIError,
    raise_for_error_response,
)


def test_insufficient_funds_exception():
    """Test InsufficientFunds exception."""
    exc = InsufficientFunds(
        message="Not enough funds",
        details={"available": "100.00", "required": "200.00"},
    )
    assert exc.status_code == 400
    assert exc.error_code == "INSUFFICIENT_FUNDS"
    assert exc.message == "Not enough funds"
    assert exc.details["available"] == "100.00"


def test_forbidden_scope_exception():
    """Test ForbiddenScope exception."""
    exc = ForbiddenScope(message="Missing transfer:create scope")
    assert exc.status_code == 403
    assert exc.error_code == "FORBIDDEN_SCOPE"


def test_limit_exceeded_exception():
    """Test LimitExceeded exception."""
    exc = LimitExceeded(
        message="Daily limit exceeded",
        details={"limit": "1000.00", "spent": "1500.00"},
    )
    assert exc.status_code == 400
    assert exc.error_code == "LIMIT_EXCEEDED"


def test_recipient_not_found_exception():
    """Test RecipientNotFound exception."""
    exc = RecipientNotFound(message="Handle @unknown not found")
    assert exc.status_code == 404
    assert exc.error_code == "RECIPIENT_NOT_FOUND"


def test_currency_mismatch_exception():
    """Test CurrencyMismatch exception."""
    exc = CurrencyMismatch(message="Wallet currency is EUR, not USD")
    assert exc.status_code == 400
    assert exc.error_code == "CURRENCY_MISMATCH"


def test_conflict_idempotency_exception():
    """Test ConflictIdempotency exception."""
    exc = ConflictIdempotency(message="Idempotency key already used")
    assert exc.status_code == 409
    assert exc.error_code == "IDEMPOTENCY_CONFLICT"


def test_raise_for_error_response_insufficient_funds():
    """Test raise_for_error_response maps INSUFFICIENT_FUNDS correctly."""
    with pytest.raises(InsufficientFunds) as exc_info:
        raise_for_error_response(
            400,
            {
                "error_code": "INSUFFICIENT_FUNDS",
                "message": "Not enough funds",
                "details": {"available": "50.00"},
            },
        )
    assert exc_info.value.message == "Not enough funds"


def test_raise_for_error_response_forbidden_scope():
    """Test raise_for_error_response maps FORBIDDEN_SCOPE correctly."""
    with pytest.raises(ForbiddenScope) as exc_info:
        raise_for_error_response(
            403,
            {
                "error_code": "FORBIDDEN_SCOPE",
                "message": "Missing required scope",
            },
        )
    assert exc_info.value.message == "Missing required scope"


def test_raise_for_error_response_unknown_error():
    """Test raise_for_error_response handles unknown error codes."""
    with pytest.raises(WalletAPIError) as exc_info:
        raise_for_error_response(
            500,
            {
                "error_code": "UNKNOWN_ERROR",
                "message": "Something went wrong",
            },
        )
    assert exc_info.value.status_code == 500
    assert exc_info.value.error_code == "UNKNOWN_ERROR"


def test_exception_str_representation():
    """Test exception string representation."""
    exc = InsufficientFunds(message="Not enough funds")
    assert str(exc) == "[400] INSUFFICIENT_FUNDS: Not enough funds"
