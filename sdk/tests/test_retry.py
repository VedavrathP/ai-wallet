"""Tests for retry behavior."""

import pytest
from unittest.mock import MagicMock, patch, call
import time

import httpx

from agent_wallet.retry import (
    calculate_backoff,
    with_retry,
    RetryableClient,
    RETRYABLE_STATUS_CODES,
    RETRYABLE_EXCEPTIONS,
)


def test_calculate_backoff_exponential():
    """Test that backoff increases exponentially."""
    # Without jitter for predictable testing
    delay_0 = calculate_backoff(0, base_delay=1.0, jitter=False)
    delay_1 = calculate_backoff(1, base_delay=1.0, jitter=False)
    delay_2 = calculate_backoff(2, base_delay=1.0, jitter=False)

    assert delay_0 == 1.0
    assert delay_1 == 2.0
    assert delay_2 == 4.0


def test_calculate_backoff_max_delay():
    """Test that backoff is capped at max_delay."""
    delay = calculate_backoff(10, base_delay=1.0, max_delay=5.0, jitter=False)
    assert delay == 5.0


def test_calculate_backoff_with_jitter():
    """Test that jitter adds randomness."""
    delays = [calculate_backoff(1, base_delay=1.0, jitter=True) for _ in range(10)]
    # With jitter, delays should vary
    assert len(set(delays)) > 1


def test_with_retry_decorator_success():
    """Test that decorator returns result on success."""
    call_count = 0

    @with_retry(max_retries=3)
    def successful_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = successful_func()
    assert result == "success"
    assert call_count == 1


def test_with_retry_decorator_retries_on_network_error():
    """Test that decorator retries on network errors."""
    call_count = 0

    @with_retry(max_retries=3, base_delay=0.01)
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection failed")
        return "success"

    result = flaky_func()
    assert result == "success"
    assert call_count == 3


def test_with_retry_decorator_gives_up_after_max_retries():
    """Test that decorator gives up after max retries."""
    call_count = 0

    @with_retry(max_retries=2, base_delay=0.01)
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("Connection failed")

    with pytest.raises(httpx.ConnectError):
        always_fails()

    assert call_count == 3  # Initial + 2 retries


def test_with_retry_decorator_no_retry_on_non_retryable():
    """Test that decorator doesn't retry non-retryable errors."""
    call_count = 0

    @with_retry(max_retries=3, base_delay=0.01)
    def raises_value_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("Not retryable")

    with pytest.raises(ValueError):
        raises_value_error()

    assert call_count == 1


def test_retryable_client_retries_on_502():
    """Test that RetryableClient retries on 502 status."""
    client = RetryableClient(max_retries=2, base_delay=0.01)
    call_count = 0

    def make_request():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            response = MagicMock()
            response.status_code = 502
            raise httpx.HTTPStatusError(
                "Bad Gateway",
                request=MagicMock(),
                response=response,
            )
        return "success"

    result = client._execute_with_retry(make_request)
    assert result == "success"
    assert call_count == 2


def test_retryable_client_no_retry_on_400():
    """Test that RetryableClient doesn't retry on 400 status."""
    client = RetryableClient(max_retries=3, base_delay=0.01)
    call_count = 0

    def make_request():
        nonlocal call_count
        call_count += 1
        response = MagicMock()
        response.status_code = 400
        raise httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=response,
        )

    with pytest.raises(httpx.HTTPStatusError):
        client._execute_with_retry(make_request)

    assert call_count == 1


def test_retryable_status_codes():
    """Test that correct status codes are marked as retryable."""
    assert 502 in RETRYABLE_STATUS_CODES
    assert 503 in RETRYABLE_STATUS_CODES
    assert 504 in RETRYABLE_STATUS_CODES
    assert 400 not in RETRYABLE_STATUS_CODES
    assert 401 not in RETRYABLE_STATUS_CODES
    assert 404 not in RETRYABLE_STATUS_CODES


def test_retryable_exceptions():
    """Test that correct exceptions are marked as retryable."""
    assert httpx.ConnectError in RETRYABLE_EXCEPTIONS
    assert httpx.ConnectTimeout in RETRYABLE_EXCEPTIONS
    assert httpx.ReadTimeout in RETRYABLE_EXCEPTIONS
    assert httpx.WriteTimeout in RETRYABLE_EXCEPTIONS
    assert httpx.PoolTimeout in RETRYABLE_EXCEPTIONS
