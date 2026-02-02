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

# Create startup script
RUN echo '#!/bin/bash\n\
echo "Running database migrations..."\n\
alembic upgrade head\n\
echo "Running seed script..."\n\
python -m agent_wallet_service.scripts.seed || echo "Seed already exists or failed"\n\
echo "Starting server..."\n\
exec uvicorn agent_wallet_service.main:app --host 0.0.0.0 --port ${PORT:-8000}\n\
' > /app/start.sh && chmod +x /app/start.sh

# Expose port (Railway uses dynamic PORT)
EXPOSE 8000

# Run startup script
CMD ["/app/start.sh"]
