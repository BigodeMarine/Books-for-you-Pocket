"""Tests for catalog service queries using an isolated SQLite database."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models import Author, Edition, EditionFormat, Genre, Work, WorkType
from app.services.catalog import get_work_by_id, list_works


@pytest.fixture
def session() -> Iterator[Session]:
    """Create a fresh in-memory SQLite schema and session for each test."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as test_session:
        yield test_session
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
    """Add a work and optional related author and genre to the test database."""
    work = Work(id=work_id or uuid4(), title=title, work_type=work_type)
    if author is not None:
        work.authors.append(author)
    if genre is not None:
        work.genres.append(genre)
    session.add(work)
    session.flush()
    return work


def test_list_works_without_filters_returns_all_in_order(session: Session) -> None:
    """Unfiltered listing returns the catalog with deterministic ordering."""
    add_work(session, "Zulu")
    add_work(session, "Alpha")

    works, total = list_works(session)

    assert [work.title for work in works] == ["Alpha", "Zulu"]
    assert total == 2


def test_list_works_search_is_partial_case_insensitive_and_strips_spaces(
    session: Session,
) -> None:
    """Title search ignores case and surrounding whitespace."""
    add_work(session, "The Left Hand of Darkness")
    add_work(session, "A Wizard of Earthsea")

    works, total = list_works(session, q="  HAND OF  ")
    blank_query_works, blank_query_total = list_works(session, q="   ")

    assert [work.title for work in works] == ["The Left Hand of Darkness"]
    assert total == 1
    assert [work.title for work in blank_query_works] == [
        "A Wizard of Earthsea",
        "The Left Hand of Darkness",
    ]
    assert blank_query_total == 2


def test_list_works_filters_by_author(session: Session) -> None:
    """Author filtering uses the work-author relationship."""
    author = Author(id=uuid4(), name="Octavia Butler")
    add_work(session, "Kindred", author=author)
    add_work(session, "Other")

    works, total = list_works(session, author_id=author.id)

    assert [work.title for work in works] == ["Kindred"]
    assert total == 1


def test_list_works_filters_by_genre(session: Session) -> None:
    """Genre filtering uses the work-genre relationship."""
    genre = Genre(id=uuid4(), name="Science fiction", slug="science-fiction")
    add_work(session, "Dawn", genre=genre)
    add_work(session, "Other")

    works, total = list_works(session, genre_id=genre.id)

    assert [work.title for work in works] == ["Dawn"]
    assert total == 1


def test_list_works_filters_by_type(session: Session) -> None:
    """Work type filtering returns only the requested enum value."""
    add_work(session, "Novel", WorkType.BOOK)
    add_work(session, "Manga", WorkType.MANGA)

    works, total = list_works(session, work_type=WorkType.MANGA)

    assert [work.title for work in works] == ["Manga"]
    assert total == 1


def test_list_works_combines_all_supplied_filters(session: Session) -> None:
    """Title, author, genre, and type filters are applied together."""
    author = Author(id=uuid4(), name="Ursula Le Guin")
    genre = Genre(id=uuid4(), name="Fantasy", slug="fantasy")
    add_work(session, "A Wizard of Earthsea", WorkType.BOOK, author=author, genre=genre)
    add_work(session, "A Wizard Manga", WorkType.MANGA, author=author, genre=genre)
    add_work(session, "A Wizard Other", WorkType.BOOK, genre=genre)

    works, total = list_works(
        session,
        q="wizard",
        author_id=author.id,
        genre_id=genre.id,
        work_type=WorkType.BOOK,
    )

    assert [work.title for work in works] == ["A Wizard of Earthsea"]
    assert total == 1


def test_list_works_paginates_with_title_then_uuid_order(session: Session) -> None:
    """Pagination follows title order and uses UUID to break title ties."""
    larger_id = UUID("00000000-0000-0000-0000-000000000002")
    smaller_id = UUID("00000000-0000-0000-0000-000000000001")
    add_work(session, "Same", work_id=larger_id)
    add_work(session, "Same", work_id=smaller_id)
    add_work(session, "Zulu")

    first_page, total = list_works(session, page=1, page_size=1)
    second_page, _ = list_works(session, page=2, page_size=1)

    assert first_page[0].id == smaller_id
    assert second_page[0].id == larger_id
    assert total == 3


def test_list_works_total_is_independent_of_page(session: Session) -> None:
    """Total count reflects all matching records, not just the current page."""
    for title in ("Book A", "Book B", "Book C"):
        add_work(session, title)

    works, total = list_works(session, q="Book", page=2, page_size=1)

    assert len(works) == 1
    assert total == 3


def test_list_works_returns_empty_results_when_no_match(session: Session) -> None:
    """No matches produce an empty page and a zero total."""
    add_work(session, "Existing")

    assert list_works(session, q="missing") == ([], 0)


def test_get_work_by_id_eagerly_loads_catalog_relationships(session: Session) -> None:
    """Detail lookup returns the work with authors, genres, and editions loaded."""
    author = Author(id=uuid4(), name="Ursula Le Guin")
    genre = Genre(id=uuid4(), name="Fantasy", slug="fantasy")
    work = add_work(session, "Earthsea", author=author, genre=genre)
    work.editions.append(
        Edition(
            id=uuid4(),
            work_id=work.id,
            language="en",
            format=EditionFormat.PAPERBACK,
        )
    )
    session.flush()

    result = get_work_by_id(session, work.id)

    assert result is not None
    assert [item.name for item in result.authors] == ["Ursula Le Guin"]
    assert [item.slug for item in result.genres] == ["fantasy"]
    assert len(result.editions) == 1
    assert result.editions[0].format is EditionFormat.PAPERBACK
    assert not {"authors", "genres", "editions"} & inspect(result).unloaded


def test_get_work_by_id_returns_none_for_unknown_uuid(session: Session) -> None:
    """A missing work is represented by None."""
    assert get_work_by_id(session, uuid4()) is None
