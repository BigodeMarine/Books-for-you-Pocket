"""SQLAlchemy model for a seller's offer on a specific edition."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AvailabilityStatus, OfferCondition, database_enum

if TYPE_CHECKING:
    from app.models.edition import Edition
    from app.models.price_history import PriceHistory
    from app.models.seller import Seller


class Offer(Base):
    """A current price and availability listing for one edition at one seller."""

    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_offers_price_nonnegative"),
        CheckConstraint(
            "original_price IS NULL OR original_price >= 0",
            name="ck_offers_original_price_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("editions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sellers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", server_default=text("'BRL'"), nullable=False)
    condition: Mapped[OfferCondition] = mapped_column(
        database_enum(OfferCondition, "offer_condition"), nullable=False
    )
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        database_enum(AvailabilityStatus, "availability_status"), nullable=False, index=True
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    edition: Mapped["Edition"] = relationship(back_populates="offers")
    seller: Mapped["Seller"] = relationship(back_populates="offers")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="offer", passive_deletes="all"
    )
