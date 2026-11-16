"""Read queries for public offers and their price history."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AvailabilityStatus,
    Edition,
    Offer,
    OfferCondition,
    PriceHistory,
    Work,
)


def list_offers(
    session: Session,
    *,
    edition_id: UUID | None = None,
    work_id: UUID | None = None,
    seller_id: UUID | None = None,
    condition: OfferCondition | None = None,
    availability_status: AvailabilityStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Offer], int] | None:
    """List active offers by edition or work; None means the parent is absent."""
    if (edition_id is None) == (work_id is None):
        raise ValueError("Exactly one of edition_id or work_id must be provided")

    parent_model = Edition if edition_id is not None else Work
    parent_id = edition_id if edition_id is not None else work_id
    if (
        session.scalar(select(parent_model.id).where(parent_model.id == parent_id))
        is None
    ):
        return None

    filters = [Offer.is_active.is_(True)]
    if edition_id is not None:
        filters.append(Offer.edition_id == edition_id)
    else:
        filters.append(
            Offer.edition_id.in_(select(Edition.id).where(Edition.work_id == work_id))
        )
    if seller_id is not None:
        filters.append(Offer.seller_id == seller_id)
    if condition is not None:
        filters.append(Offer.condition == condition)
    if availability_status is not None:
        filters.append(Offer.availability_status == availability_status)

    total = session.scalar(select(func.count()).select_from(Offer).where(*filters)) or 0
    statement = (
        select(Offer)
        .where(*filters)
        .options(selectinload(Offer.seller))
        .order_by(Offer.price.asc(), Offer.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(statement).all()), total


def get_offer(session: Session, offer_id: UUID) -> Offer | None:
    """Return an active offer with its seller loaded, or None if unavailable."""
    statement = (
        select(Offer)
        .where(Offer.id == offer_id, Offer.is_active.is_(True))
        .options(selectinload(Offer.seller))
    )
    return session.scalar(statement)


def list_price_history(
    session: Session,
    offer_id: UUID,
    *,
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PriceHistory], int] | None:
    """List snapshots for an active offer; None means the offer is unavailable."""
    active_offer_id = session.scalar(
        select(Offer.id).where(Offer.id == offer_id, Offer.is_active.is_(True))
    )
    if active_offer_id is None:
        return None

    filters = [PriceHistory.offer_id == offer_id]
    if captured_from is not None:
        filters.append(PriceHistory.captured_at >= captured_from)
    if captured_to is not None:
        filters.append(PriceHistory.captured_at <= captured_to)

    total = (
        session.scalar(select(func.count()).select_from(PriceHistory).where(*filters))
        or 0
    )
    statement = (
        select(PriceHistory)
        .where(*filters)
        .order_by(PriceHistory.captured_at.desc(), PriceHistory.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(statement).all()), total
