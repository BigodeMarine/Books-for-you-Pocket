"""Tests for Pydantic catalog response schemas."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.models import (
    Author,
    Edition,
    EditionFormat,
    Genre,
    MetadataSource,
    Work,
    WorkType,
)
from app.schemas.catalog import (
    AuthorRead,
    GenreRead,
    PaginatedResponse,
    WorkDetailRead,
    WorkListItemRead,
)


def test_author_and_genre_schemas_build_from_models() -> None:
    """Author and genre schemas read their declared model attributes."""
    author = Author(id=uuid4(), name="Ursula K. Le Guin")
    genre = Genre(id=uuid4(), name="Fantasia", slug="fantasia")

    author_schema = AuthorRead.model_validate(author)
    genre_schema = GenreRead.model_validate(genre)

    assert author_schema.name == author.name
    assert genre_schema.model_dump() == {
        "id": genre.id,
        "name": "Fantasia",
        "slug": "fantasia",
    }


def test_work_schemas_convert_sqlalchemy_attributes_and_relationships() -> None:
    """Work schemas convert enums and nested catalog relationships."""
    work_id = uuid4()
    work = Work(
        id=work_id,
        title="A Wizard of Earthsea",
        subtitle=None,
        description="A fantasy novel.",
        work_type=WorkType.BOOK,
        original_language="en",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    work.editions = [
        Edition(
            id=uuid4(),
            work_id=work_id,
            isbn_10=None,
            isbn_13="9780547773742",
            publisher="Houghton Mifflin",
            language="en",
            format=EditionFormat.PAPERBACK,
            volume_number=None,
            publication_date=date(2012, 2, 22),
            page_count=205,
            cover_url=None,
            metadata_source=MetadataSource.MANUAL,
            metadata_external_id=None,
            metadata_updated_at=None,
        )
    ]
    work.authors = [Author(id=uuid4(), name="Ursula K. Le Guin")]
    work.genres = [Genre(id=uuid4(), name="Fantasia", slug="fantasia")]

    list_item = WorkListItemRead.model_validate(work)
    detail = WorkDetailRead.model_validate(work)

    assert list_item.work_type is WorkType.BOOK
    assert "description" not in list_item.model_dump()
    assert detail.editions[0].format is EditionFormat.PAPERBACK
    assert detail.authors[0].name == "Ursula K. Le Guin"
    assert detail.genres[0].slug == "fantasia"
    assert detail.editions[0].isbn_10 is None
    assert detail.editions[0].cover_url is None
    assert detail.editions[0].metadata_updated_at is None


def test_schema_json_serializes_uuid_enums_and_dates() -> None:
    """JSON output uses string enum values and ISO date/time values."""
    work = WorkListItemRead(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Book",
        subtitle=None,
        work_type=WorkType.MANGA,
        original_language=None,
    )

    assert work.model_dump(mode="json") == {
        "id": "00000000-0000-0000-0000-000000000001",
        "title": "Book",
        "subtitle": None,
        "work_type": "manga",
        "original_language": None,
    }


def test_paginated_response_preserves_typed_items_and_metadata() -> None:
    """Generic pagination schemas retain their item type and page values."""
    item = WorkListItemRead(
        id=uuid4(),
        title="Book",
        subtitle=None,
        work_type=WorkType.BOOK,
        original_language="pt-BR",
    )

    response = PaginatedResponse[WorkListItemRead](
        items=[item], total=1, page=1, page_size=20, total_pages=1
    )

    assert isinstance(response.items[0], WorkListItemRead)
    assert response.model_dump(mode="json")["items"][0]["work_type"] == "book"
    assert response.total == 1
    assert response.page == 1
    assert response.page_size == 20
    assert response.total_pages == 1
