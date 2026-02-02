"""API key model."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.wallet import Wallet


class APIKeyStatus(str, enum.Enum):
    """API key status enumeration."""

    ACTIVE = "active"
    REVOKED = "revoked"


class APIKey(Base):
    """API key model for authentication and authorization."""

    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    key_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        unique=True,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    limits: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    status: Mapped[APIKeyStatus] = mapped_column(
        Enum(APIKeyStatus, name="api_key_status"),
        nullable=False,
        default=APIKeyStatus.ACTIVE,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="api_keys",
    )

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, wallet_id={self.wallet_id}, status={self.status})>"

    def has_scope(self, required_scope: str) -> bool:
        """Check if the API key has the required scope.

        Supports wildcard scopes like 'admin:*' which matches any admin scope.
        """
        if not self.scopes:
            return False

        for scope in self.scopes:
            if scope == required_scope:
                return True
            # Check wildcard scopes
            if scope.endswith(":*"):
                prefix = scope[:-1]  # Remove the '*'
                if required_scope.startswith(prefix):
                    return True

        return False

    def get_limit(self, limit_name: str, default: Any = None) -> Any:
        """Get a limit value by name."""
        if not self.limits:
            return default
        return self.limits.get(limit_name, default)
