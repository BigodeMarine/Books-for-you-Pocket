"""HTTP integration tests for importing Google Books volumes."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import catalog_imports
from app.api.routes.catalog_imports import get_book_provider
from app.core.database import Base, get_db
from app.main import app
from app.models import Edition, EditionExternalIdentifier, Work, WorkType
from app.schemas.catalog_imports import GoogleBooksImportRequest
from app.schemas.external_books import ExternalBookRead
from app.services.external_books.base import (
    BookProviderError,
    BookProviderQuotaExceeded,
    BookProviderTimeout,
)
from app.services.google_books_import import persist_google_books_import


class FakeBookProvider:
    """Deterministic provider that never performs network requests."""

    def __init__(self) -> None:
        self.volume: ExternalBookRead | None = ExternalBookRead(
            provider_id="volume-1",
            title="Earthsea",
            authors=["Ursula K. Le Guin"],
            published_date="1968",
            language="en",
        )
        self.error: BookProviderError | None = None
        self.calls: list[str] = []

    async def search(
        self, *args: object, **kwargs: object
    ) -> tuple[list[ExternalBookRead], int]:
        return [], 0

    async def get_by_id(self, provider_id: str) -> ExternalBookRead | None:
        self.calls.append(provider_id)
        if self.error is not None:
            raise self.error
        return self.volume


@pytest.fixture
def api_context() -> Iterator[
    tuple[TestClient, FakeBookProvider, sessionmaker[Session]]
]:
    """Provide a client and isolated in-memory database, restoring overrides."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    provider = FakeBookProvider()
    previous_db = app.dependency_overrides.get(get_db)
    previous_provider = app.dependency_overrides.get(get_book_provider)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_book_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            yield client, provider, factory
    finally:
        if previous_db is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db
        if previous_provider is None:
            app.dependency_overrides.pop(get_book_provider, None)
        else:
            app.dependency_overrides[get_book_provider] = previous_provider
        engine.dispose()


def request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "provider_id": "volume-1",
        "work_target": {"kind": "new", "work_type": "book"},
        "edition_format": "paperback",
        "language_fallback": "en",
    }
    payload.update(overrides)
    return payload


def seed_work(factory: sessionmaker[Session]) -> UUID:
    with factory() as session:
        work = Work(title="A Wizard of Earthsea", work_type=WorkType.BOOK)
        session.add(work)
        session.commit()
        return work.id


def seed_import(factory: sessionmaker[Session]) -> tuple[UUID, UUID]:
    volume = FakeBookProvider().volume
    assert volume is not None
    with factory() as session:
        request = GoogleBooksImportRequest.model_validate(request_payload())
        with session.begin():
            result = persist_google_books_import(session, request, volume)
        return result.work_id, result.edition_id


def test_creates_work_and_edition_with_created_status(api_context: object) -> None:
    client, provider, factory = api_context  # type: ignore[misc]
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )

    assert response.status_code == 201
    assert response.json()["work_created"] is True
    assert response.json()["edition_created"] is True
    assert provider.calls == ["volume-1"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Work)) == 1
        assert session.scalar(select(func.count()).select_from(Edition)) == 1


def test_imports_into_existing_work(api_context: object) -> None:
    client, _, factory = api_context  # type: ignore[misc]
    work_id = seed_work(factory)
    response = client.post(
        "/api/v1/catalog/imports/google-books",
        json=request_payload(work_target={"kind": "existing", "work_id": str(work_id)}),
    )

    assert response.status_code == 201
    assert response.json()["work_id"] == str(work_id)
    assert response.json()["work_created"] is False
    assert response.json()["edition_created"] is True


def test_reuses_existing_import_with_ok_status(api_context: object) -> None:
    client, _, factory = api_context  # type: ignore[misc]
    work_id, edition_id = seed_import(factory)
    response = client.post(
        "/api/v1/catalog/imports/google-books",
        json=request_payload(work_target={"kind": "existing", "work_id": str(work_id)}),
    )

    assert response.status_code == 200
    assert response.json()["work_id"] == str(work_id)
    assert response.json()["edition_id"] == str(edition_id)
    assert response.json()["edition_created"] is False


def test_returns_service_warnings(api_context: object) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    assert provider.volume is not None
    provider.volume = provider.volume.model_copy(
        update={"published_date": "1968-13-45"}
    )
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )

    assert response.status_code == 201
    assert response.json()["warnings"][0]["code"] == "publication_date_invalid"


def test_rejects_invalid_request(api_context: object) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    response = client.post(
        "/api/v1/catalog/imports/google-books",
        json={
            "provider_id": "volume-1",
            "work_target": {"kind": "new", "work_type": "book"},
            "extra": True,
        },
    )

    assert response.status_code == 422
    assert provider.calls == []


def test_missing_volume_returns_not_found(api_context: object) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    provider.volume = None
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )
    assert response.status_code == 404


def test_missing_work_returns_not_found(api_context: object) -> None:
    client, _, _ = api_context  # type: ignore[misc]
    response = client.post(
        "/api/v1/catalog/imports/google-books",
        json=request_payload(work_target={"kind": "existing", "work_id": str(uuid4())}),
    )
    assert response.status_code == 404


def test_conflicting_destination_returns_conflict(api_context: object) -> None:
    client, _, factory = api_context  # type: ignore[misc]
    seed_import(factory)
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"edition_format": None}, 422),
        ({"language_fallback": None}, 422),
    ],
)
def test_requires_format_and_language(
    api_context: object, overrides: dict[str, object], expected_status: int
) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    if "language_fallback" in overrides:
        assert provider.volume is not None
        provider.volume = provider.volume.model_copy(update={"language": None})
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload(**overrides)
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("provider_error", "expected_status"),
    [
        (BookProviderQuotaExceeded("private quota"), 503),
        (BookProviderTimeout("private timeout"), 504),
        (BookProviderError("private provider detail"), 502),
    ],
)
def test_maps_provider_errors_without_leaking_details(
    api_context: object,
    provider_error: BookProviderError,
    expected_status: int,
) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    provider.error = provider_error
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )

    assert response.status_code == expected_status
    assert "private" not in response.text


def test_invalid_provider_id_returns_unprocessable(api_context: object) -> None:
    client, _, _ = api_context  # type: ignore[misc]
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload(provider_id="   ")
    )
    assert response.status_code == 422


def test_provider_volume_id_mismatch_returns_unprocessable(api_context: object) -> None:
    client, provider, _ = api_context  # type: ignore[misc]
    assert provider.volume is not None
    provider.volume = provider.volume.model_copy(update={"provider_id": "other-volume"})
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )
    assert response.status_code == 422


def test_unexpected_persistence_failure_rolls_back_everything(
    api_context: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, factory = api_context  # type: ignore[misc]

    def fail_after_partial_write(
        session: Session, request: GoogleBooksImportRequest, volume: ExternalBookRead
    ) -> object:
        session.add(Work(title="partial", work_type=WorkType.BOOK))
        session.flush()
        raise RuntimeError("sensitive internal failure")

    monkeypatch.setattr(
        catalog_imports, "persist_google_books_import", fail_after_partial_write
    )
    response = client.post(
        "/api/v1/catalog/imports/google-books", json=request_payload()
    )

    assert response.status_code == 500
    assert "sensitive internal failure" not in response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Work)) == 0
        assert session.scalar(select(func.count()).select_from(Edition)) == 0
        assert (
            session.scalar(select(func.count()).select_from(EditionExternalIdentifier))
            == 0
        )
