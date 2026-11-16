"""HTTP endpoints for catalog queries."""

from datetime import datetime
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import AvailabilityStatus, OfferCondition, WorkType
from app.schemas.catalog import PaginatedResponse, WorkDetailRead, WorkListItemRead
from app.schemas.offers import OfferRead, PriceHistoryRead
from app.services.catalog import get_work_by_id, list_works
from app.services.offers import get_offer, list_offers, list_price_history

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])
T = TypeVar("T")


@router.get("/works", response_model=PaginatedResponse[WorkListItemRead])
def read_works(
    session: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    author_id: UUID | None = None,
    genre_id: UUID | None = None,
    work_type: WorkType | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[WorkListItemRead]:
    """Return a filtered and paginated list of works."""
    works, total = list_works(
        session,
        q=q,
        author_id=author_id,
        genre_id=genre_id,
        work_type=work_type,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse[WorkListItemRead](
        items=works,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/works/{work_id}", response_model=WorkDetailRead)
def read_work(
    work_id: UUID, session: Annotated[Session, Depends(get_db)]
) -> WorkDetailRead:
    """Return one work with its editions, authors, and genres."""
    work = get_work_by_id(session, work_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return WorkDetailRead.model_validate(work)


def _paginated_response(
    items: list[T], total: int, page: int, page_size: int, item_schema: type[T]
) -> PaginatedResponse[T]:
    """Build the shared catalog pagination envelope for a typed item schema."""
    response_schema = PaginatedResponse[item_schema]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return response_schema(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/editions/{edition_id}/offers", response_model=PaginatedResponse[OfferRead]
)
def read_edition_offers(
    edition_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    seller_id: UUID | None = None,
    condition: OfferCondition | None = None,
    availability_status: AvailabilityStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[OfferRead]:
    """List active offers for one edition, ordered by ascending price."""
    result = list_offers(
        session,
        edition_id=edition_id,
        seller_id=seller_id,
        condition=condition,
        availability_status=availability_status,
        page=page,
        page_size=page_size,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Edition not found")
    offers, total = result
    return _paginated_response(offers, total, page, page_size, OfferRead)


@router.get("/works/{work_id}/offers", response_model=PaginatedResponse[OfferRead])
def read_work_offers(
    work_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    seller_id: UUID | None = None,
    condition: OfferCondition | None = None,
    availability_status: AvailabilityStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[OfferRead]:
    """List active offers across every edition of a work."""
    result = list_offers(
        session,
        work_id=work_id,
        seller_id=seller_id,
        condition=condition,
        availability_status=availability_status,
        page=page,
        page_size=page_size,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Work not found")
    offers, total = result
    return _paginated_response(offers, total, page, page_size, OfferRead)


@router.get("/offers/{offer_id}", response_model=OfferRead)
def read_offer(
    offer_id: UUID, session: Annotated[Session, Depends(get_db)]
) -> OfferRead:
    """Return the details of an active offer, including its seller."""
    offer = get_offer(session, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return OfferRead.model_validate(offer)


@router.get(
    "/offers/{offer_id}/price-history",
    response_model=PaginatedResponse[PriceHistoryRead],
)
def read_offer_price_history(
    offer_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[PriceHistoryRead]:
    """List an active offer's snapshots, newest first, optionally by period."""
    if (
        captured_from is not None
        and captured_to is not None
        and captured_from > captured_to
    ):
        raise HTTPException(
            status_code=422,
            detail="captured_from must be less than or equal to captured_to",
        )
    result = list_price_history(
        session,
        offer_id,
        captured_from=captured_from,
        captured_to=captured_to,
        page=page,
        page_size=page_size,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    snapshots, total = result
    return _paginated_response(snapshots, total, page, page_size, PriceHistoryRead)
