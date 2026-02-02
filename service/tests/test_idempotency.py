"""Tests for idempotency behavior."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transfer_idempotency_same_result(client: AsyncClient, funded_customer: dict):
    """Test that same idempotency key returns same result."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # First transfer
    response1 = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_idempotency_001",
        },
    )
    assert response1.status_code == 200
    result1 = response1.json()

    # Second transfer with same idempotency key
    response2 = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_idempotency_001",
        },
    )
    assert response2.status_code == 200
    result2 = response2.json()

    # Results should be identical
    assert result1["id"] == result2["id"]
    assert result1["journal_entry_id"] == result2["journal_entry_id"]


@pytest.mark.asyncio
async def test_transfer_different_idempotency_keys(client: AsyncClient, funded_customer: dict):
    """Test that different idempotency keys create different transfers."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # First transfer
    response1 = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "25.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_idempotency_002",
        },
    )
    assert response1.status_code == 200
    result1 = response1.json()

    # Second transfer with different idempotency key
    response2 = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "25.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_idempotency_003",
        },
    )
    assert response2.status_code == 200
    result2 = response2.json()

    # Results should be different
    assert result1["id"] != result2["id"]


@pytest.mark.asyncio
async def test_hold_idempotency(client: AsyncClient, funded_customer: dict):
    """Test hold idempotency."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]

    # First hold
    response1 = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_hold_idempotency_001",
            "expires_in_seconds": 3600,
        },
    )
    assert response1.status_code == 200
    result1 = response1.json()

    # Second hold with same idempotency key
    response2 = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_hold_idempotency_001",
            "expires_in_seconds": 3600,
        },
    )
    assert response2.status_code == 200
    result2 = response2.json()

    # Results should be identical
    assert result1["id"] == result2["id"]
