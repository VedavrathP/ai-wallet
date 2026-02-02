"""External identity model for mapping external user IDs to wallets."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_wallet_service.db.session import Base

if TYPE_CHECKING:
    from agent_wallet_service.models.wallet import Wallet


class ExternalIdentity(Base):
    """External identity mapping external user IDs from partner systems to wallets."""

    __tablename__ = "external_identities"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    external_user_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="external_identities",
    )

    __table_args__ = (
        UniqueConstraint("provider", "external_user_id", name="uq_external_identity"),
    )

    def __repr__(self) -> str:
        return f"<ExternalIdentity(provider={self.provider}, external_user_id={self.external_user_id})>"
