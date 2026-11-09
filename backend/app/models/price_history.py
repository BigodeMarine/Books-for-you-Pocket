"""SQLAlchemy model for captured offer prices and availability."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AvailabilityStatus, database_enum

if TYPE_CHECKING:
    from app.models.offer import Offer


class PriceHistory(Base):
    """A price and availability snapshot retained for an offer."""

    __tablename__ = "price_history"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_price_history_price_nonnegative"),
        CheckConstraint(
            "original_price IS NULL OR original_price >= 0",
            name="ck_price_history_original_price_nonnegative",
        ),
        Index("ix_price_history_offer_captured_at", "offer_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("offers.id", ondelete="RESTRICT"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        database_enum(AvailabilityStatus, "availability_status"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    offer: Mapped["Offer"] = relationship(back_populates="price_history")
