"""Tests for limit enforcement."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_per_transaction_limit(client: AsyncClient, funded_customer: dict):
    """Test that per-transaction limit is enforced."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Customer has per_tx_max of $500
    response = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "600.00",  # Exceeds $500 limit
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_per_tx_limit",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_within_per_transaction_limit(client: AsyncClient, funded_customer: dict):
    """Test that transfers within limit succeed."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Customer has per_tx_max of $500
    response = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "400.00",  # Within $500 limit
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_within_per_tx_limit",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_hold_respects_per_transaction_limit(client: AsyncClient, funded_customer: dict):
    """Test that holds also respect per-transaction limit."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]

    # Customer has per_tx_max of $500
    response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "600.00",  # Exceeds $500 limit
            "currency": "USD",
            "idempotency_key": "test_hold_per_tx_limit",
            "expires_in_seconds": 3600,
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "LIMIT_EXCEEDED"
