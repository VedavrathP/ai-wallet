"""Tests for refund operations."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import Capture


@pytest.mark.asyncio
async def test_refund_against_capture(
    client: AsyncClient, db_session: AsyncSession, funded_customer: dict
):
    """Test creating a refund against a capture."""
    customer_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_refund_hold",
            "expires_in_seconds": 3600,
        },
    )
    hold_id = hold_response.json()["id"]

    # Capture hold
    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_refund_capture",
        },
    )
    capture_id = capture_response.json()["id"]

    # Merchant issues refund
    refund_response = await client.post(
        "/v1/refunds",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "capture_id": capture_id,
            "idempotency_key": "test_refund_001",
            "amount": "50.00",  # Partial refund
        },
    )

    assert refund_response.status_code == 200
    refund = refund_response.json()
    assert refund["amount"] == "50.00"
    assert refund["capture_id"] == capture_id


@pytest.mark.asyncio
async def test_refund_full_amount(
    client: AsyncClient, db_session: AsyncSession, funded_customer: dict
):
    """Test refunding the full capture amount."""
    customer_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create and capture hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "amount": "75.00",
            "currency": "USD",
            "idempotency_key": "test_full_refund_hold",
            "expires_in_seconds": 3600,
        },
    )
    hold_id = hold_response.json()["id"]

    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_full_refund_capture",
        },
    )
    capture_id = capture_response.json()["id"]

    # Full refund (no amount specified)
    refund_response = await client.post(
        "/v1/refunds",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "capture_id": capture_id,
            "idempotency_key": "test_full_refund",
        },
    )

    assert refund_response.status_code == 200
    refund = refund_response.json()
    assert refund["amount"] == "75.00"


@pytest.mark.asyncio
async def test_refund_exceeds_capture(
    client: AsyncClient, db_session: AsyncSession, funded_customer: dict
):
    """Test that refund cannot exceed capture amount."""
    customer_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create and capture hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "idempotency_key": "test_exceed_refund_hold",
            "expires_in_seconds": 3600,
        },
    )
    hold_id = hold_response.json()["id"]

    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_exceed_refund_capture",
        },
    )
    capture_id = capture_response.json()["id"]

    # Try to refund more than captured
    refund_response = await client.post(
        "/v1/refunds",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "capture_id": capture_id,
            "idempotency_key": "test_exceed_refund",
            "amount": "100.00",
        },
    )

    assert refund_response.status_code == 400
    assert refund_response.json()["error_code"] == "AMOUNT_EXCEEDS_REFUNDABLE"


@pytest.mark.asyncio
async def test_only_merchant_can_refund(client: AsyncClient, funded_customer: dict):
    """Test that only the merchant can issue refunds."""
    customer_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create and capture hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "idempotency_key": "test_merchant_only_hold",
            "expires_in_seconds": 3600,
        },
    )
    hold_id = hold_response.json()["id"]

    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_merchant_only_capture",
        },
    )
    capture_id = capture_response.json()["id"]

    # Customer tries to refund (should fail - no refund:create scope)
    refund_response = await client.post(
        "/v1/refunds",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "capture_id": capture_id,
            "idempotency_key": "test_customer_refund",
        },
    )

    assert refund_response.status_code == 403
