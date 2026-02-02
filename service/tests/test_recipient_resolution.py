"""Tests for recipient resolution."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_resolve_by_handle(client: AsyncClient, funded_customer: dict):
    """Test resolving recipient by handle."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    response = await client.get(
        "/v1/resolve",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"type": "handle", "value": merchant_handle},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["handle"] == merchant_handle
    assert data["type"] == "business"


@pytest.mark.asyncio
async def test_resolve_by_wallet_id(client: AsyncClient, funded_customer: dict):
    """Test resolving recipient by wallet ID."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_wallet_id = str(funded_customer["wallets"]["merchant"].id)

    response = await client.get(
        "/v1/resolve",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"type": "wallet_id", "value": merchant_wallet_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["wallet_id"] == merchant_wallet_id


@pytest.mark.asyncio
async def test_resolve_unknown_handle(client: AsyncClient, funded_customer: dict):
    """Test resolving unknown handle returns 404."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]

    response = await client.get(
        "/v1/resolve",
        headers={"Authorization": f"Bearer {api_key}"},
        params={"type": "handle", "value": "@nonexistent"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "RECIPIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_transfer_to_handle(client: AsyncClient, funded_customer: dict):
    """Test transfer using handle addressing."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    response = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "25.00",
            "currency": "USD",
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_transfer_handle",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["to_wallet_id"] == str(funded_customer["wallets"]["merchant"].id)


@pytest.mark.asyncio
async def test_transfer_to_wallet_id(client: AsyncClient, funded_customer: dict):
    """Test transfer using wallet ID addressing."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_wallet_id = str(funded_customer["wallets"]["merchant"].id)

    response = await client.post(
        "/v1/transfers",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "25.00",
            "currency": "USD",
            "to": {"type": "wallet_id", "value": merchant_wallet_id},
            "idempotency_key": "test_transfer_wallet_id",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["to_wallet_id"] == merchant_wallet_id
