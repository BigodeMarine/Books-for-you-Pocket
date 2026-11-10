"""Integration tests for the catalog HTTP API."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import Author, Edition, EditionFormat, Genre, Work, WorkType


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Provide a client backed by an isolated in-memory SQLite database."""
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


def add_work(
    session: Session,
    title: str,
    work_type: WorkType = WorkType.BOOK,
    *,
    author: Author | None = None,
    genre: Genre | None = None,
    work_id: UUID | None = None,
) -> Work:
    """Persist a work and optional catalog relations for a request test."""
    work = Work(id=work_id or uuid4(), title=title, work_type=work_type)
    if author is not None:
        work.authors.append(author)
    if genre is not None:
        work.genres.append(genre)
    session.add(work)
    session.flush()
    return work


def seed_catalog(client: TestClient) -> tuple[UUID, UUID, UUID]:
    """Create related and unrelated works through the overridden test session."""
    dependency = app.dependency_overrides[get_db]
    session_dependency = dependency()
    session = next(session_dependency)
    try:
        author = Author(id=uuid4(), name="Ursula Le Guin")
        genre = Genre(id=uuid4(), name="Fantasy", slug="fantasy")
        work = add_work(
            session,
            "A Wizard of Earthsea",
            author=author,
            genre=genre,
        )
        work.editions.append(
            Edition(
                id=uuid4(),
                work_id=work.id,
                language="en",
                format=EditionFormat.PAPERBACK,
            )
        )
        add_work(session, "The Left Hand of Darkness", WorkType.BOOK, author=author)
        add_work(session, "Other Manga", WorkType.MANGA)
        identifiers = work.id, author.id, genre.id
        session.commit()
        return identifiers
    finally:
        session_dependency.close()


def test_list_works_without_filters(client: TestClient) -> None:
    """Listing returns the default page envelope and all catalog works."""
    seed_catalog(client)

    response = client.get("/api/v1/catalog/works")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["total_pages"] == 1
    assert len(payload["items"]) == 3


def test_list_works_searches_title(client: TestClient) -> None:
    """The title query is delegated to the catalog service."""
    seed_catalog(client)

    response = client.get("/api/v1/catalog/works", params={"q": "wizard"})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == [
        "A Wizard of Earthsea"
    ]


def test_list_works_filters_by_author(client: TestClient) -> None:
    """Author UUID filter returns works associated with that author."""
    _, author_id, _ = seed_catalog(client)

    response = client.get("/api/v1/catalog/works", params={"author_id": str(author_id)})

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_list_works_filters_by_genre(client: TestClient) -> None:
    """Genre UUID filter returns works associated with that genre."""
    _, _, genre_id = seed_catalog(client)

    response = client.get("/api/v1/catalog/works", params={"genre_id": str(genre_id)})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == [
        "A Wizard of Earthsea"
    ]


def test_list_works_filters_by_work_type(client: TestClient) -> None:
    """Work type enum values are accepted and applied by the service."""
    seed_catalog(client)

    response = client.get("/api/v1/catalog/works", params={"work_type": "manga"})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Other Manga"]


def test_list_works_combines_filters(client: TestClient) -> None:
    """Multiple query filters are passed together to the catalog service."""
    _, author_id, genre_id = seed_catalog(client)

    response = client.get(
        "/api/v1/catalog/works",
        params={
            "q": "wizard",
            "author_id": str(author_id),
            "genre_id": str(genre_id),
            "work_type": "book",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "A Wizard of Earthsea"


def test_list_works_pagination_and_metadata(client: TestClient) -> None:
    """Pagination returns the requested slice and calculated page metadata."""
    seed_catalog(client)

    response = client.get(
        "/api/v1/catalog/works", params={"page": 2, "page_size": 2}
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 2
    assert response.json()["total_pages"] == 2
    assert len(response.json()["items"]) == 1


def test_list_works_accepts_maximum_page_size(client: TestClient) -> None:
    """The documented maximum page size of 100 is accepted."""
    response = client.get("/api/v1/catalog/works", params={"page_size": 100})

    assert response.status_code == 200
    assert response.json()["page_size"] == 100


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": 101},
        {"work_type": "unknown"},
        {"author_id": "bad-uuid"},
        {"genre_id": "bad-uuid"},
    ],
)
def test_invalid_list_parameters_return_422(
    client: TestClient, params: dict[str, str | int]
) -> None:
    """Invalid pagination, enum, and UUID query values are rejected."""
    response = client.get("/api/v1/catalog/works", params=params)

    assert response.status_code == 422


def test_list_works_empty_response_has_zero_pages(client: TestClient) -> None:
    """No matches return an empty page with zero total pages."""
    response = client.get("/api/v1/catalog/works", params={"q": "absent"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }


def test_get_work_details_includes_editions_authors_and_genres(
    client: TestClient,
) -> None:
    """Detail response serializes the related catalog entities."""
    work_id, _, _ = seed_catalog(client)

    response = client.get(f"/api/v1/catalog/works/{work_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(work_id)
    assert payload["authors"][0]["name"] == "Ursula Le Guin"
    assert payload["genres"][0]["slug"] == "fantasy"
    assert payload["editions"][0]["format"] == "paperback"


def test_get_unknown_work_returns_404(client: TestClient) -> None:
    """A valid but absent UUID maps to a clear not-found response."""
    response = client.get(f"/api/v1/catalog/works/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Work not found"


def test_malformed_work_uuid_returns_422(client: TestClient) -> None:
    """Malformed UUID path parameters are rejected by FastAPI validation."""
    response = client.get("/api/v1/catalog/works/not-a-uuid")

    assert response.status_code == 422


def test_health_endpoint_is_preserved(client: TestClient) -> None:
    """The existing health endpoint remains available after router registration."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
