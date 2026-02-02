"""Tests for hold operations."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_wallet_service.models import Hold, LedgerAccount
from agent_wallet_service.models.hold import HoldStatus
from agent_wallet_service.models.ledger_account import LedgerAccountKind
from agent_wallet_service.services.balance import get_ledger_account_balance


@pytest.mark.asyncio
async def test_create_hold(client: AsyncClient, funded_customer: dict):
    """Test creating a hold."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]

    response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_create_hold_001",
            "expires_in_seconds": 3600,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "100.00"
    assert data["remaining_amount"] == "100.00"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_hold_capture_partial(
    client: AsyncClient, db_session: AsyncSession, funded_customer: dict
):
    """Test partial capture of a hold."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_partial_capture_hold",
            "expires_in_seconds": 3600,
        },
    )
    assert hold_response.status_code == 200
    hold_id = hold_response.json()["id"]

    # Capture partial amount
    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_partial_capture",
            "amount": "60.00",
        },
    )
    assert capture_response.status_code == 200
    capture_data = capture_response.json()
    assert capture_data["amount"] == "60.00"

    # Check hold remaining amount
    result = await db_session.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one()
    assert hold.remaining_amount == Decimal("40.00")
    assert hold.status == HoldStatus.ACTIVE


@pytest.mark.asyncio
async def test_hold_capture_release_remainder(
    client: AsyncClient, db_session: AsyncSession, funded_customer: dict
):
    """Test capturing part of a hold and releasing the remainder."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle
    customer_wallet_id = funded_customer["wallets"]["customer"].id

    # Get initial balance
    result = await db_session.execute(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == customer_wallet_id,
            LedgerAccount.kind == LedgerAccountKind.AVAILABLE,
        )
    )
    available_account = result.scalar_one()
    initial_available = await get_ledger_account_balance(db_session, available_account.id)

    # Create hold for $100
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "test_capture_release_hold",
            "expires_in_seconds": 3600,
        },
    )
    assert hold_response.status_code == 200
    hold_id = hold_response.json()["id"]

    # Capture $70
    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_capture_70",
            "amount": "70.00",
        },
    )
    assert capture_response.status_code == 200

    # Release remainder ($30)
    release_response = await client.post(
        f"/v1/holds/{hold_id}/release",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "idempotency_key": "test_release_30",
        },
    )
    assert release_response.status_code == 200
    release_data = release_response.json()
    assert release_data["amount"] == "30.00"

    # Check hold is fully processed
    result = await db_session.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one()
    assert hold.remaining_amount == Decimal("0")
    assert hold.status == HoldStatus.RELEASED

    # Check final balance (initial - 70 captured)
    final_available = await get_ledger_account_balance(db_session, available_account.id)
    assert final_available == initial_available - Decimal("70.00")


@pytest.mark.asyncio
async def test_hold_insufficient_funds(client: AsyncClient, funded_customer: dict):
    """Test hold fails with insufficient funds."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]

    response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "5000.00",  # More than $1000 balance
            "currency": "USD",
            "idempotency_key": "test_hold_insufficient",
            "expires_in_seconds": 3600,
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INSUFFICIENT_FUNDS"


@pytest.mark.asyncio
async def test_capture_exceeds_remaining(client: AsyncClient, funded_customer: dict):
    """Test capture fails when amount exceeds remaining hold."""
    api_key = funded_customer["api_keys"]["customer"]["raw"]
    merchant_handle = funded_customer["wallets"]["merchant"].handle

    # Create hold
    hold_response = await client.post(
        "/v1/holds",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "idempotency_key": "test_capture_exceeds_hold",
            "expires_in_seconds": 3600,
        },
    )
    hold_id = hold_response.json()["id"]

    # Try to capture more than hold amount
    capture_response = await client.post(
        f"/v1/holds/{hold_id}/capture",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "to": {"type": "handle", "value": merchant_handle},
            "idempotency_key": "test_capture_exceeds",
            "amount": "100.00",
        },
    )

    assert capture_response.status_code == 400
    assert capture_response.json()["error_code"] == "AMOUNT_EXCEEDS_HOLD"
