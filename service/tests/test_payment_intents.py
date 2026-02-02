"""Tests for payment intent flow."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_payment_intent_full_flow(client: AsyncClient, funded_customer: dict):
    """Test complete payment intent flow: create -> pay."""
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    customer_key = funded_customer["api_keys"]["customer"]["raw"]

    # Merchant creates payment intent
    create_response = await client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "amount": "75.00",
            "currency": "USD",
            "expires_in_seconds": 900,
            "metadata": {"order_id": "test_order_001"},
        },
    )

    assert create_response.status_code == 200
    intent = create_response.json()
    assert intent["status"] == "requires_payment"
    intent_id = intent["id"]

    # Customer pays the intent
    pay_response = await client.post(
        f"/v1/payment_intents/{intent_id}/pay",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "idempotency_key": "test_pay_intent_001",
        },
    )

    assert pay_response.status_code == 200
    result = pay_response.json()
    assert result["payment_intent_id"] == intent_id
    assert result["amount"] == "75.00"


@pytest.mark.asyncio
async def test_payment_intent_insufficient_funds(client: AsyncClient, funded_customer: dict):
    """Test payment intent fails with insufficient funds."""
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    customer_key = funded_customer["api_keys"]["customer"]["raw"]

    # Merchant creates large payment intent
    create_response = await client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "amount": "5000.00",  # More than customer's $1000
            "currency": "USD",
            "expires_in_seconds": 900,
        },
    )

    assert create_response.status_code == 200
    intent_id = create_response.json()["id"]

    # Customer tries to pay
    pay_response = await client.post(
        f"/v1/payment_intents/{intent_id}/pay",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={
            "idempotency_key": "test_pay_insufficient",
        },
    )

    assert pay_response.status_code == 400
    assert pay_response.json()["error_code"] == "INSUFFICIENT_FUNDS"


@pytest.mark.asyncio
async def test_payment_intent_already_paid(client: AsyncClient, funded_customer: dict):
    """Test that payment intent can only be paid once."""
    merchant_key = funded_customer["api_keys"]["merchant"]["raw"]
    customer_key = funded_customer["api_keys"]["customer"]["raw"]

    # Create and pay intent
    create_response = await client.post(
        "/v1/payment_intents",
        headers={"Authorization": f"Bearer {merchant_key}"},
        json={
            "amount": "50.00",
            "currency": "USD",
            "expires_in_seconds": 900,
        },
    )
    intent_id = create_response.json()["id"]

    # First payment
    await client.post(
        f"/v1/payment_intents/{intent_id}/pay",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={"idempotency_key": "test_pay_first"},
    )

    # Second payment attempt (different idempotency key)
    pay_response = await client.post(
        f"/v1/payment_intents/{intent_id}/pay",
        headers={"Authorization": f"Bearer {customer_key}"},
        json={"idempotency_key": "test_pay_second"},
    )

    assert pay_response.status_code == 400
    assert pay_response.json()["error_code"] == "PAYMENT_INTENT_NOT_PAYABLE"
