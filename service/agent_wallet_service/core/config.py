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

    # Database - Railway provides DATABASE_URL, we convert it for asyncpg
    DATABASE_URL: str = "postgresql+asyncpg://wallet_user:wallet_secret@localhost:5432/agent_wallet"

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """Get async database URL (converts postgresql:// to postgresql+asyncpg://)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Get sync database URL for Alembic."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # Remove asyncpg if present
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url

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
