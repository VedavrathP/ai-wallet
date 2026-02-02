"""FastAPI application entry point."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Log startup info
logger.info("Starting Agent Wallet API...")
logger.info(f"Python version: {sys.version}")
logger.info(f"PORT env var: {os.environ.get('PORT', 'not set')}")
logger.info(f"DATABASE_URL set: {'DATABASE_URL' in os.environ}")

from agent_wallet_service.core.config import settings

logger.info(f"Database URL (masked): {settings.DATABASE_URL_ASYNC[:30]}...")

from agent_wallet_service.api.v1 import router as v1_router
from agent_wallet_service.db.session import engine

logger.info("All imports successful")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Application startup complete")
    yield
    # Shutdown
    logger.info("Application shutting down...")
    await engine.dispose()


app = FastAPI(
    title="Agent Wallet API",
    description="Production-grade financial ledger API with double-entry accounting",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(v1_router, prefix="/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
