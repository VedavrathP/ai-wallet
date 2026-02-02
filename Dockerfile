FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy service dependency files and README (required by pyproject.toml)
COPY service/pyproject.toml .
COPY service/README.md .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy service application code
COPY service/agent_wallet_service ./agent_wallet_service
COPY service/alembic.ini .
COPY service/alembic ./alembic

# Expose port
EXPOSE 8000

# Default command - Railway sets PORT env var
CMD uvicorn agent_wallet_service.main:app --host 0.0.0.0 --port ${PORT:-8000}
