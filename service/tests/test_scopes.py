"""Tests for scope enforcement."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transfer_requires_scope(client: AsyncClient, funded_customer: dict):
    """Test that transfer requires transfer:create scope."""
    # Use limited key (only has wallet:read)
    limited_key = funded_customer["api_keys"]["limited"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    response = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {limited_key}"},
        json={
            "amount": "10.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_scope_transfer",
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


@pytest.mark.asyncio
async def test_hold_requires_scope(client: AsyncClient, funded_customer: dict):
    """Test that hold requires hold:create scope."""
    limited_key = funded_customer["api_keys"]["limited"]["raw"]

    response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {limited_key}"},
        json={
            "amount": "10.00",
            "currency": "USD",
            "idempotency_key": "test_scope_hold",
            "expires_in_seconds": 3600,
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


@pytest.mark.asyncio
async def test_balance_allowed_with_read_scope(client: AsyncClient, funded_customer: dict):
    """Test that balance check is allowed with wallet:read scope."""
    limited_key = funded_customer["api_keys"]["limited"]["raw"]

    response = await client.get(
        "/v1/wallets/me/balance",
        headers={"Authorization": f"Bearer {limited_key}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "held" in data


@pytest.mark.asyncio
async def test_payment_intent_create_requires_scope(client: AsyncClient, funded_customer: dict):
    """Test that payment intent creation requires payment_intent:create scope."""
    customer_key = funded_customer["api_keys"]["customer"]["raw"]

    response = await client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "expires_in_seconds": 900,
        },
    )

    # Customer doesn't have payment_intent:create scope
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


@pytest.mark.asyncio
async def test_merchant_can_create_payment_intent(client: AsyncClient, funded_customer: dict):
    """Test that merchant can create payment intent."""
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]

    response = await client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "expires_in_seconds": 900,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "50.00"
    assert data["status"] == "requires_payment"
