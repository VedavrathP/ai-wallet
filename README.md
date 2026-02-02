# Agent Wallet Platform

A production-grade financial ledger system with double-entry accounting, API key authentication, and a Python SDK for agent interactions.

## Architecture

The platform consists of two main components:

1. **Service** (`service/`) - FastAPI backend with PostgreSQL database
2. **SDK** (`sdk/`) - Python client library published to PyPI

### Key Features

- **Double-Entry Accounting**: All transactions are recorded as immutable journal entries with balanced debits and credits
- **Idempotency**: All write operations require idempotency keys to prevent duplicate transactions
- **Concurrency Safety**: Uses `SELECT ... FOR UPDATE` to prevent double-spend scenarios
- **API Key Authentication**: Scoped permissions with rate limiting and spending limits
- **Recipient Resolution**: Support for wallet IDs, handles (@username), and external identifiers

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+

### Running Locally

```bash
# Start PostgreSQL and the service
docker-compose up -d

# The API will be available at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### Seeding Test Data

```bash
# Run the seed script to create test wallets and API keys
docker-compose exec service python -m agent_wallet_service.scripts.seed
```

This creates:
- Customer wallet `@alice` with $1000 balance
- Merchant wallet `@acme_store`
- API keys for both wallets (printed to console)

## API Overview

### Authentication

All API requests require a Bearer token:

```bash
curl -H "Authorization: Bearer <api_key>" http://localhost:8000/v1/wallets/me
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/wallets/me` | Get current wallet info |
| GET | `/v1/wallets/me/balance` | Get wallet balance |
| GET | `/v1/wallets/me/transactions` | List transactions |
| POST | `/v1/transfers` | Create a transfer |
| POST | `/v1/holds` | Create a hold |
| POST | `/v1/holds/{id}/capture` | Capture a hold |
| POST | `/v1/holds/{id}/release` | Release a hold |
| POST | `/v1/payment_intents` | Create payment intent |
| POST | `/v1/payment_intents/{id}/pay` | Pay a payment intent |
| POST | `/v1/refunds` | Create a refund |

## SDK Usage

Install the SDK:

```bash
pip install agent-wallet
```

Basic usage:

```python
from agent_wallet import WalletClient

client = WalletClient(
    api_key="your_api_key",
    base_url="http://localhost:8000"
)

# Check balance
balance = client.balance()
print(f"Available: {balance.available} {balance.currency}")

# Transfer funds
transfer = client.transfer(
    to_handle="@acme_store",
    amount="12.50",
    currency="USD",
    idempotency_key="unique-key-123"
)

# Create a hold
hold = client.hold(
    amount="50.00",
    currency="USD",
    idempotency_key="hold-key-456",
    expires_in_seconds=600
)

# Capture the hold
capture = client.capture(
    hold_id=hold.id,
    to_handle="@acme_store",
    idempotency_key="capture-key-789"
)
```

## Concurrency Control

The system uses pessimistic locking (`SELECT ... FOR UPDATE`) on ledger accounts to prevent double-spend scenarios. This approach:

1. Acquires exclusive locks on affected ledger accounts at the start of a transaction
2. Derives current balance from journal lines
3. Validates sufficient funds
4. Creates journal entries atomically
5. Releases locks on commit

This ensures that concurrent transactions on the same wallet are serialized, preventing race conditions.

## Development

### Running Tests

```bash
# Backend tests
cd service
pytest

# SDK tests
cd sdk
pytest
```

### Database Migrations

```bash
# Create a new migration
cd service
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## License

MIT License
