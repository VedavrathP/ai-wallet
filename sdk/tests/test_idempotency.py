"""Tests for idempotency header propagation."""

import pytest
from unittest.mock import MagicMock, patch

import httpx

from agent_wallet import WalletClient


def test_transfer_sends_idempotency_header():
    """Test that transfer sends Idempotency-Key header."""
    with patch.object(httpx.Client, "request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "txn_123",
            "journal_entry_id": "je_123",
            "from_wallet_id": "wallet_1",
            "to_wallet_id": "wallet_2",
            "amount": "50.00",
            "currency": "USD",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = WalletClient(api_key="test_key", base_url="http://test")
        client.transfer(
            to_handle="@merchant",
            amount="50.00",
            currency="USD",
            idempotency_key="test_key_123",
        )

        # Check that Idempotency-Key header was sent
        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Idempotency-Key"] == "test_key_123"


def test_hold_sends_idempotency_header():
    """Test that hold sends Idempotency-Key header."""
    with patch.object(httpx.Client, "request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "hold_123",
            "wallet_id": "wallet_1",
            "amount": "100.00",
            "remaining_amount": "100.00",
            "currency": "USD",
            "status": "active",
            "expires_at": "2024-01-01T01:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = WalletClient(api_key="test_key", base_url="http://test")
        client.hold(
            amount="100.00",
            currency="USD",
            idempotency_key="hold_key_456",
        )

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["Idempotency-Key"] == "hold_key_456"


def test_capture_sends_idempotency_header():
    """Test that capture sends Idempotency-Key header."""
    with patch.object(httpx.Client, "request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cap_123",
            "hold_id": "hold_123",
            "to_wallet_id": "wallet_2",
            "amount": "100.00",
            "currency": "USD",
            "journal_entry_id": "je_456",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = WalletClient(api_key="test_key", base_url="http://test")
        client.capture(
            hold_id="hold_123",
            to_handle="@merchant",
            idempotency_key="capture_key_789",
        )

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["Idempotency-Key"] == "capture_key_789"


def test_pay_payment_intent_sends_idempotency_header():
    """Test that pay_payment_intent sends Idempotency-Key header."""
    with patch.object(httpx.Client, "request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "payment_intent_id": "pi_123",
            "journal_entry_id": "je_789",
            "payer_wallet_id": "wallet_1",
            "merchant_wallet_id": "wallet_2",
            "amount": "75.00",
            "currency": "USD",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = WalletClient(api_key="test_key", base_url="http://test")
        client.pay_payment_intent(
            intent_id="pi_123",
            idempotency_key="pay_key_101",
        )

        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["Idempotency-Key"] == "pay_key_101"


def test_balance_does_not_send_idempotency_header():
    """Test that balance (GET request) does not send Idempotency-Key header."""
    with patch.object(httpx.Client, "request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "wallet_id": "wallet_1",
            "available": "1000.00",
            "held": "0.00",
            "total": "1000.00",
            "currency": "USD",
        }
        mock_request.return_value = mock_response

        client = WalletClient(api_key="test_key", base_url="http://test")
        client.balance()

        call_kwargs = mock_request.call_args[1]
        # Headers should be empty for GET requests without idempotency
        assert call_kwargs.get("headers", {}).get("Idempotency-Key") is None
