"""Pydantic response schemas for offers and price history."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AvailabilityStatus, OfferCondition


class SellerRead(BaseModel):
    """Public seller information embedded in offer responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    website_url: str | None
    logo_url: str | None
    is_active: bool


class OfferRead(BaseModel):
    """Public representation of an active edition offer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    edition_id: UUID
    seller: SellerRead
    external_id: str | None
    url: str
    price: Decimal
    original_price: Decimal | None
    currency: str
    condition: OfferCondition
    availability_status: AvailabilityStatus
    last_checked_at: datetime


class PriceHistoryRead(BaseModel):
    """Public representation of one captured price snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    offer_id: UUID
    price: Decimal
    original_price: Decimal | None
    availability_status: AvailabilityStatus
    captured_at: datetime
