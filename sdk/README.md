# Agent Wallet SDK

Python SDK for the Agent Wallet API - secure financial operations for AI agents.

## Installation

```bash
pip install agent-wallet
```

## Quick Start

```python
from agent_wallet import WalletClient

# Initialize the client
client = WalletClient(
    api_key="aw_your_api_key_here",
    base_url="http://localhost:8000"
)

# Check your balance
balance = client.balance()
print(f"Available: {balance.available} {balance.currency}")
print(f"Held: {balance.held} {balance.currency}")
print(f"Total: {balance.total} {balance.currency}")
```

## Features

- **Type-safe**: Full type hints and Pydantic models for all responses
- **Idempotent**: Built-in support for idempotency keys to prevent duplicate transactions
- **Retry logic**: Automatic retries with exponential backoff for network errors
- **Clean exceptions**: Specific exception classes for different error types

## Usage Examples

### Transfer Funds

```python
transfer = client.transfer(
    to_handle="@merchant",
    amount="25.00",
    currency="USD",
    idempotency_key="unique-transfer-key-123",
    reference_id="order_456",
    metadata={"note": "Payment for order"}
)
print(f"Transfer ID: {transfer.id}")
```

### Create and Capture a Hold

```python
# Create a hold (reservation)
hold = client.hold(
    amount="100.00",
    currency="USD",
    idempotency_key="hold-key-789",
    expires_in_seconds=3600  # 1 hour
)
print(f"Hold ID: {hold.id}")

# Capture the hold (partial or full)
capture = client.capture(
    hold_id=hold.id,
    to_handle="@merchant",
    amount="75.00",  # Capture only $75 of the $100 hold
    idempotency_key="capture-key-101"
)

# Release the remaining hold
release = client.release(
    hold_id=hold.id,
    idempotency_key="release-key-102"
)
```

### Payment Intents (Merchant Flow)

```python
# Merchant creates a payment intent
intent = client.create_payment_intent(
    amount="50.00",
    currency="USD",
    expires_in_seconds=900,  # 15 minutes
    metadata={"order_id": "order_789"}
)
print(f"Payment Intent ID: {intent.id}")

# Customer pays the intent
result = client.pay_payment_intent(
    intent_id=intent.id,
    idempotency_key="pay-intent-key-103"
)
```

### Request a Refund

```python
refund = client.refund(
    capture_id="cap_abc123",
    amount="25.00",  # Partial refund
    idempotency_key="refund-key-104"
)
print(f"Refund ID: {refund.id}")
```

## Exception Handling

```python
from agent_wallet import WalletClient
from agent_wallet.exceptions import (
    InsufficientFunds,
    ForbiddenScope,
    LimitExceeded,
    RecipientNotFound,
    CurrencyMismatch,
    ConflictIdempotency,
    WalletAPIError,
)

client = WalletClient(api_key="...", base_url="...")

try:
    transfer = client.transfer(
        to_handle="@merchant",
        amount="1000000.00",
        currency="USD",
        idempotency_key="key-123"
    )
except InsufficientFunds as e:
    print(f"Not enough funds: {e.message}")
except LimitExceeded as e:
    print(f"Transaction limit exceeded: {e.message}")
except RecipientNotFound as e:
    print(f"Recipient not found: {e.message}")
except ForbiddenScope as e:
    print(f"Permission denied: {e.message}")
except CurrencyMismatch as e:
    print(f"Currency mismatch: {e.message}")
except ConflictIdempotency as e:
    print(f"Idempotency conflict: {e.message}")
except WalletAPIError as e:
    print(f"API error: {e.status_code} - {e.message}")
```

## Configuration

### Custom Timeout

```python
client = WalletClient(
    api_key="...",
    base_url="...",
    timeout=30.0  # 30 seconds
)
```

### Disable Retries

```python
client = WalletClient(
    api_key="...",
    base_url="...",
    max_retries=0
)
```

## API Reference

### WalletClient Methods

| Method | Description |
|--------|-------------|
| `balance()` | Get current wallet balance |
| `transactions(cursor, limit)` | List transactions with pagination |
| `transfer(...)` | Transfer funds to another wallet |
| `hold(...)` | Create a hold/reservation |
| `capture(...)` | Capture a hold |
| `release(...)` | Release a hold |
| `create_payment_intent(...)` | Create a payment intent |
| `pay_payment_intent(...)` | Pay a payment intent |
| `refund(...)` | Request a refund |

## License

MIT License
