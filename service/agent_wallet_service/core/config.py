"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://wallet_user:wallet_secret@localhost:5432/agent_wallet"
    DATABASE_URL_SYNC: str = "postgresql://wallet_user:wallet_secret@localhost:5432/agent_wallet"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY_PREFIX: str = "aw_"

    # Application
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["*"]

    # Rate limiting (requests per minute per API key)
    RATE_LIMIT_RPM: int = 100

    # Default limits
    DEFAULT_PER_TX_MAX: str = "10000.00"
    DEFAULT_DAILY_MAX: str = "100000.00"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
