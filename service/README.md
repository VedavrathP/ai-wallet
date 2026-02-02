# Agent Wallet Service

FastAPI backend service for the Agent Wallet platform.

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker (optional, for containerized development)

### Local Development

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -e ".[dev]"
```

3. Set up environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://wallet_user:wallet_secret@localhost:5432/agent_wallet"
export DATABASE_URL_SYNC="postgresql://wallet_user:wallet_secret@localhost:5432/agent_wallet"
```

4. Run database migrations:

```bash
alembic upgrade head
```

5. Seed the database:

```bash
python -m agent_wallet_service.scripts.seed
```

6. Start the server:

```bash
uvicorn agent_wallet_service.main:app --reload
```

### Using Docker

```bash
# From the repository root
docker-compose up -d
```

## API Documentation

Once the server is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agent_wallet_service --cov-report=html

# Run specific test file
pytest tests/test_idempotency.py
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Project Structure

```
agent_wallet_service/
├── api/                  # API endpoints
│   └── v1/              # Version 1 endpoints
├── core/                # Configuration
├── db/                  # Database session
├── middleware/          # Auth, rate limiting, audit
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
├── scripts/             # Seed and maintenance scripts
└── utils/               # Utilities
```
