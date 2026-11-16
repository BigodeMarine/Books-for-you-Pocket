"""Integration tests for public offer and price-history queries."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import (
    AvailabilityStatus,
    Edition,
    EditionFormat,
    Offer,
    OfferCondition,
    PriceHistory,
    Seller,
    Work,
    WorkType,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide an isolated API client backed by in-memory SQLite."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def seed_offers(client: TestClient) -> dict[str, UUID]:
    """Create a work with two editions, sellers, active offers, and history."""
    session_dependency = app.dependency_overrides[get_db]()
    session = next(session_dependency)
    try:
        work = Work(id=uuid4(), title="Earthsea", work_type=WorkType.BOOK)
        edition_one = Edition(
            id=uuid4(), work_id=work.id, language="en", format=EditionFormat.PAPERBACK
        )
        edition_two = Edition(
            id=uuid4(),
            work_id=work.id,
            language="pt-BR",
            format=EditionFormat.HARDCOVER,
        )
        other_work = Work(id=uuid4(), title="Other", work_type=WorkType.BOOK)
        other_edition = Edition(
            id=uuid4(), work_id=other_work.id, language="en", format=EditionFormat.EBOOK
        )
        seller_a = Seller(id=uuid4(), name="Loja A", slug="loja-a")
        seller_b = Seller(id=uuid4(), name="Loja B", slug="loja-b")
        offer_low = Offer(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            edition_id=edition_one.id,
            seller_id=seller_a.id,
            url="https://shop.test/low",
            price=Decimal("10.00"),
            condition=OfferCondition.NEW,
            availability_status=AvailabilityStatus.IN_STOCK,
        )
        offer_same_price = Offer(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            edition_id=edition_one.id,
            seller_id=seller_b.id,
            url="https://shop.test/same",
            price=Decimal("10.00"),
            condition=OfferCondition.USED,
            availability_status=AvailabilityStatus.OUT_OF_STOCK,
        )
        offer_second_edition = Offer(
            id=uuid4(),
            edition_id=edition_two.id,
            seller_id=seller_a.id,
            url="https://shop.test/second",
            price=Decimal("15.00"),
            condition=OfferCondition.NEW,
            availability_status=AvailabilityStatus.PREORDER,
        )
        inactive_offer = Offer(
            id=uuid4(),
            edition_id=edition_one.id,
            seller_id=seller_a.id,
            url="https://shop.test/inactive",
            price=Decimal("1.00"),
            condition=OfferCondition.NEW,
            availability_status=AvailabilityStatus.IN_STOCK,
            is_active=False,
        )
        orphan_scope_offer = Offer(
            id=uuid4(),
            edition_id=other_edition.id,
            seller_id=seller_a.id,
            url="https://shop.test/other",
            price=Decimal("5.00"),
            condition=OfferCondition.NEW,
            availability_status=AvailabilityStatus.IN_STOCK,
        )
        session.add_all(
            [
                work,
                edition_one,
                edition_two,
                other_work,
                other_edition,
                seller_a,
                seller_b,
            ]
        )
        session.flush()
        session.add_all(
            [
                offer_low,
                offer_same_price,
                offer_second_edition,
                inactive_offer,
                orphan_scope_offer,
            ]
        )
        base_time = datetime(2026, 1, 1, tzinfo=UTC)
        session.add_all(
            [
                PriceHistory(
                    id=UUID("00000000-0000-0000-0000-000000000011"),
                    offer_id=offer_low.id,
                    price=Decimal("12.00"),
                    availability_status=AvailabilityStatus.IN_STOCK,
                    captured_at=base_time,
                ),
                PriceHistory(
                    id=UUID("00000000-0000-0000-0000-000000000012"),
                    offer_id=offer_low.id,
                    price=Decimal("10.00"),
                    availability_status=AvailabilityStatus.IN_STOCK,
                    captured_at=base_time + timedelta(days=1),
                ),
                PriceHistory(
                    id=UUID("00000000-0000-0000-0000-000000000013"),
                    offer_id=offer_low.id,
                    price=Decimal("10.00"),
                    availability_status=AvailabilityStatus.IN_STOCK,
                    captured_at=base_time + timedelta(days=1),
                ),
            ]
        )
        session.commit()
        return {
            "work": work.id,
            "edition": edition_one.id,
            "second_edition": edition_two.id,
            "seller_a": seller_a.id,
            "seller_b": seller_b.id,
            "offer": offer_low.id,
            "same_price_offer": offer_same_price.id,
            "second_edition_offer": offer_second_edition.id,
            "inactive_offer": inactive_offer.id,
        }
    finally:
        session_dependency.close()


def test_list_offers_by_edition_sorts_and_serializes_seller(client: TestClient) -> None:
    """Edition listing sorts by price and embeds seller response data."""
    ids = seed_offers(client)

    response = client.get(f"/api/v1/catalog/editions/{ids['edition']}/offers")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [
        str(ids["offer"]),
        str(ids["same_price_offer"]),
    ]
    assert payload["items"][0]["seller"]["id"] == str(ids["seller_a"])
    assert payload["items"][0]["seller"]["slug"] == "loja-a"
    assert payload["total"] == 2


def test_list_offers_by_work_includes_all_editions(client: TestClient) -> None:
    """Work listing aggregates offers for both of its editions only."""
    ids = seed_offers(client)

    response = client.get(f"/api/v1/catalog/works/{ids['work']}/offers")

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert {item["edition_id"] for item in response.json()["items"]} == {
        str(ids["edition"]),
        str(ids["second_edition"]),
    }


def test_offer_detail_returns_active_offer_with_seller(client: TestClient) -> None:
    """Offer detail includes nested seller information."""
    ids = seed_offers(client)

    response = client.get(f"/api/v1/catalog/offers/{ids['offer']}")

    assert response.status_code == 200
    assert response.json()["id"] == str(ids["offer"])
    assert response.json()["seller"]["name"] == "Loja A"


def test_active_offer_remains_visible_when_seller_is_inactive(
    client: TestClient,
) -> None:
    """Offer activity controls visibility while seller activity stays informational."""
    ids = seed_offers(client)
    session_dependency = app.dependency_overrides[get_db]()
    session = next(session_dependency)
    try:
        seller = session.get(Seller, ids["seller_b"])
        assert seller is not None
        seller.is_active = False
        session.commit()
    finally:
        session_dependency.close()

    response = client.get(f"/api/v1/catalog/offers/{ids['same_price_offer']}")

    assert response.status_code == 200
    assert response.json()["seller"]["is_active"] is False


def test_offer_filters_and_pagination(client: TestClient) -> None:
    """Seller, condition, availability, and the shared page metadata are applied."""
    ids = seed_offers(client)

    response = client.get(
        f"/api/v1/catalog/works/{ids['work']}/offers",
        params={
            "seller_id": str(ids["seller_a"]),
            "condition": "new",
            "availability_status": "in_stock",
            "page": 2,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["page"] == 2
    assert response.json()["items"] == []
    assert response.json()["total_pages"] == 1


def test_offer_pages_return_results_in_deterministic_order(client: TestClient) -> None:
    """Successive one-item pages use price order and UUID to break price ties."""
    ids = seed_offers(client)
    url = f"/api/v1/catalog/works/{ids['work']}/offers"
    pages = [
        client.get(url, params={"page": page, "page_size": 1}) for page in (1, 2, 3)
    ]

    assert all(response.status_code == 200 for response in pages)
    assert all(len(response.json()["items"]) == 1 for response in pages)
    assert [response.json()["items"][0]["id"] for response in pages] == [
        str(ids["offer"]),
        str(ids["same_price_offer"]),
        str(ids["second_edition_offer"]),
    ]
    assert all(response.json()["total"] == 3 for response in pages)


def test_offer_list_empty_results_use_zero_page_count(client: TestClient) -> None:
    """A valid edition without matches returns the standard empty page shape."""
    ids = seed_offers(client)

    response = client.get(
        f"/api/v1/catalog/editions/{ids['edition']}/offers",
        params={"seller_id": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == response.json()["total_pages"] == 0


def test_price_history_filters_period_and_orders_deterministically(
    client: TestClient,
) -> None:
    """History period bounds apply inclusively and ties use ascending UUID."""
    ids = seed_offers(client)
    start = datetime(2026, 1, 2, tzinfo=UTC)

    response = client.get(
        f"/api/v1/catalog/offers/{ids['offer']}/price-history",
        params={"captured_from": start.isoformat(), "captured_to": start.isoformat()},
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [
        "00000000-0000-0000-0000-000000000012",
        "00000000-0000-0000-0000-000000000013",
    ]
    assert response.json()["items"][0]["price"] == "10.00"


def test_reversed_price_history_period_returns_422(client: TestClient) -> None:
    """A start after the end is rejected as an invalid query interval."""
    ids = seed_offers(client)

    response = client.get(
        f"/api/v1/catalog/offers/{ids['offer']}/price-history",
        params={
            "captured_from": "2026-01-03T00:00:00Z",
            "captured_to": "2026-01-02T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "captured_from must be less than or equal to captured_to"
    )


def test_price_history_pagination_and_empty_period(client: TestClient) -> None:
    """History uses standard pagination and returns an empty page for no period match."""
    ids = seed_offers(client)

    newest_first = client.get(f"/api/v1/catalog/offers/{ids['offer']}/price-history")
    page = client.get(
        f"/api/v1/catalog/offers/{ids['offer']}/price-history",
        params={"page": 2, "page_size": 1},
    )
    empty = client.get(
        f"/api/v1/catalog/offers/{ids['offer']}/price-history",
        params={"captured_from": "2027-01-01T00:00:00Z"},
    )

    assert newest_first.status_code == page.status_code == empty.status_code == 200
    assert [row["id"] for row in newest_first.json()["items"]] == [
        "00000000-0000-0000-0000-000000000012",
        "00000000-0000-0000-0000-000000000013",
        "00000000-0000-0000-0000-000000000011",
    ]
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1
    assert empty.json()["items"] == []
    assert empty.json()["total_pages"] == 0


def test_inactive_offer_is_hidden_from_all_public_queries(client: TestClient) -> None:
    """Inactive offers are excluded from lists, detail, and historical access."""
    ids = seed_offers(client)

    listing = client.get(f"/api/v1/catalog/editions/{ids['edition']}/offers")
    detail = client.get(f"/api/v1/catalog/offers/{ids['inactive_offer']}")
    history = client.get(
        f"/api/v1/catalog/offers/{ids['inactive_offer']}/price-history"
    )

    assert listing.status_code == 200
    assert str(ids["inactive_offer"]) not in {
        row["id"] for row in listing.json()["items"]
    }
    assert detail.status_code == history.status_code == 404


@pytest.mark.parametrize(
    ("path", "expected_detail"),
    [
        ("/api/v1/catalog/editions/{id}/offers", "Edition not found"),
        ("/api/v1/catalog/works/{id}/offers", "Work not found"),
        ("/api/v1/catalog/offers/{id}", "Offer not found"),
        (
            "/api/v1/catalog/offers/{id}/price-history",
            "Offer not found",
        ),
    ],
)
def test_unknown_resource_ids_return_404(
    client: TestClient, path: str, expected_detail: str
) -> None:
    """Every resource-scoped endpoint returns a clear 404 for an unknown UUID."""
    response = client.get(path.format(id=uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == expected_detail


def test_health_endpoint_remains_available(client: TestClient) -> None:
    """Health remains available after marketplace routes are registered."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
