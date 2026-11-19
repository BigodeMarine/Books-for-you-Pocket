"""Tests for the Google Books import service foundation."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models import (
    Author,
    Edition,
    EditionExternalIdentifier,
    EditionFormat,
    ExternalIdentifierSource,
    Genre,
    MetadataSource,
    Work,
    WorkType,
)
from app.schemas.catalog_imports import (
    ExistingWorkTarget,
    GoogleBooksImportRequest,
    NewWorkTarget,
)
from app.schemas.external_books import ExternalBookRead
from app.services.external_books.base import BookProviderError, BookProviderTimeout
from app.services.google_books_import import (
    ExistingEditionMatch,
    GoogleBooksVolumeNotFound,
    ImportDestinationConflict,
    ImportEditionFormatRequired,
    ImportLanguageRequired,
    ImportProviderIdInvalid,
    ImportProviderIdMismatch,
    ImportWorkNotFound,
    ensure_work_target_compatible,
    fetch_google_books_volume,
    find_edition_by_google_books_id,
    is_valid_isbn_10,
    is_valid_isbn_13,
    isbn_10_to_13,
    normalize_isbn_10,
    normalize_isbn_13,
    persist_google_books_import,
)


class FakeBookProvider:
    """Provider fake that returns a configured result or provider failure."""

    def __init__(
        self,
        result: ExternalBookRead | None = None,
        error: BookProviderError | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.requested_ids: list[str] = []

    async def get_by_id(self, provider_id: str) -> ExternalBookRead | None:
        self.requested_ids.append(provider_id)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def session() -> Iterator[Session]:
    """Create an isolated in-memory SQLite schema and session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        yield db
    engine.dispose()


def add_edition(
    session: Session, *, title: str = "Earthsea", provider_id: str | None = None
) -> Edition:
    """Create a work and edition, optionally linked to a Google Books ID."""
    work = Work(title=title, work_type=WorkType.BOOK)
    edition = Edition(
        work=work,
        language="en",
        format=EditionFormat.PAPERBACK,
    )
    if provider_id is not None:
        edition.external_identifiers.append(
            EditionExternalIdentifier(
                source=ExternalIdentifierSource.GOOGLE_BOOKS,
                external_id=provider_id,
            )
        )
    session.add(edition)
    session.flush()
    return edition


def test_fetch_volume_returns_provider_result() -> None:
    """Volume lookup delegates to the provider with the requested ID."""
    volume = ExternalBookRead(provider_id="volume-1", title="Earthsea")
    provider = FakeBookProvider(result=volume)

    result = asyncio.run(fetch_google_books_volume(provider, " volume-1 "))

    assert result is volume
    assert provider.requested_ids == ["volume-1"]


def test_fetch_volume_raises_specific_error_when_missing() -> None:
    """A provider miss is represented by the service's not-found exception."""
    provider = FakeBookProvider(result=None)

    with pytest.raises(GoogleBooksVolumeNotFound):
        asyncio.run(fetch_google_books_volume(provider, "missing-volume"))

    assert provider.requested_ids == ["missing-volume"]


def test_fetch_volume_propagates_provider_errors() -> None:
    """Provider failures pass through without translation in the service helper."""
    error = BookProviderTimeout()
    provider = FakeBookProvider(error=error)

    with pytest.raises(BookProviderTimeout) as raised:
        asyncio.run(fetch_google_books_volume(provider, "volume-1"))

    assert raised.value is error


def test_find_edition_by_external_identifier_returns_detached_ids(
    session: Session,
) -> None:
    """The lookup returns edition/work IDs for the matching Google identifier."""
    edition = add_edition(session, provider_id="volume-1")
    expected = ExistingEditionMatch(edition_id=edition.id, work_id=edition.work_id)

    result = find_edition_by_google_books_id(session, "volume-1")

    assert result == expected
    assert result is not None


def test_find_edition_by_external_identifier_returns_none_when_absent(
    session: Session,
) -> None:
    """No matching external identifier returns None, even for a matching title."""
    add_edition(session, title="Same title, unrelated provider record")

    result = find_edition_by_google_books_id(session, "volume-1")

    assert result is None


def test_find_edition_does_not_create_or_modify_records(session: Session) -> None:
    """Identifier resolution issues reads only and leaves catalog rows unchanged."""
    edition = add_edition(session, provider_id="volume-1")
    before = (
        session.scalar(select(func.count()).select_from(Work)),
        session.scalar(select(func.count()).select_from(Edition)),
        session.scalar(select(func.count()).select_from(EditionExternalIdentifier)),
        edition.work.title,
        edition.language,
        edition.format,
    )
    statements: list[str] = []

    @event.listens_for(session.get_bind(), "before_cursor_execute")
    def record_statement(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement.lower())

    result = find_edition_by_google_books_id(session, "volume-1")

    after = (
        session.scalar(select(func.count()).select_from(Work)),
        session.scalar(select(func.count()).select_from(Edition)),
        session.scalar(select(func.count()).select_from(EditionExternalIdentifier)),
        edition.work.title,
        edition.language,
        edition.format,
    )
    assert result is not None
    assert after == before
    assert all(
        statement.lstrip().startswith("select")
        for statement in statements
    )
    assert all("works.title" not in statement for statement in statements)


def test_ensure_work_target_accepts_matching_existing_work() -> None:
    """An existing target is compatible only when its UUID matches the edition."""
    work_id = uuid4()
    target = ExistingWorkTarget(kind="existing", work_id=work_id)
    edition = ExistingEditionMatch(edition_id=uuid4(), work_id=work_id)

    ensure_work_target_compatible(target, edition)


def test_ensure_work_target_rejects_different_existing_work() -> None:
    """A target naming another work raises a domain conflict."""
    target = ExistingWorkTarget(kind="existing", work_id=uuid4())
    edition = ExistingEditionMatch(edition_id=uuid4(), work_id=uuid4())

    with pytest.raises(ImportDestinationConflict):
        ensure_work_target_compatible(target, edition)


def test_ensure_work_target_rejects_new_work_for_existing_edition() -> None:
    """An edition already linked to a work conflicts with a new-work target."""
    target = NewWorkTarget(kind="new", work_type=WorkType.BOOK)
    edition = ExistingEditionMatch(edition_id=uuid4(), work_id=uuid4())

    with pytest.raises(ImportDestinationConflict):
        ensure_work_target_compatible(target, edition)


def test_persist_import_reuses_existing_edition_without_changes(
    session: Session,
) -> None:
    """An external ID match returns existing IDs without creating records."""
    edition = add_edition(session, provider_id="volume-1")
    edition.metadata_source = None
    edition.metadata_external_id = "legacy-value"
    original_edition_id = edition.id
    original_work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-1",
        work_target=ExistingWorkTarget(kind="existing", work_id=original_work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-1", title="New title"),
        )
        assert session.in_transaction()

    assert result.work_id == original_work_id
    assert result.edition_id == original_edition_id
    assert result.work_created is False
    assert result.edition_created is False
    assert session.scalar(select(func.count()).select_from(Work)) == 1

    assert session.scalar(select(func.count()).select_from(Edition)) == 1
    assert session.scalar(select(func.count()).select_from(EditionExternalIdentifier)) == 1
    stored = session.get(Edition, original_edition_id)
    assert stored is not None
    assert stored.metadata_source is None
    assert stored.metadata_external_id == "legacy-value"


@pytest.mark.parametrize(
    "target",
    [
        ExistingWorkTarget(kind="existing", work_id=uuid4()),
        NewWorkTarget(kind="new", work_type=WorkType.BOOK),
    ],
    ids=["different-existing-work", "new-work-target"],
)
def test_persist_import_rejects_incompatible_existing_edition_target(
    session: Session, target: ExistingWorkTarget | NewWorkTarget
) -> None:
    """A conflicting target fails before creating or changing catalog records."""
    add_edition(session, provider_id="volume-1")
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-1",
        work_target=target,
    )

    with pytest.raises(ImportDestinationConflict), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-1", title="Earthsea"),
        )

    assert session.scalar(select(func.count()).select_from(Work)) == 1
    assert session.scalar(select(func.count()).select_from(Edition)) == 1
    assert session.scalar(select(func.count()).select_from(EditionExternalIdentifier)) == 1


def test_persist_import_creates_edition_for_existing_work(session: Session) -> None:
    """An existing target receives an edition without changing work attributes."""
    work = Work(title="Earthsea", work_type=WorkType.BOOK, description="Keep me")
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-2",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.HARDCOVER,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="volume-2", title="Provider title", language="fr"
            ),
        )

    stored_work = session.get(Work, work_id)
    edition = session.get(Edition, result.edition_id)
    assert stored_work is not None
    assert stored_work.title == "Earthsea"
    assert stored_work.description == "Keep me"
    assert result.work_created is False
    assert result.edition_created is True
    assert edition is not None
    assert edition.work_id == work_id
    assert edition.format is EditionFormat.HARDCOVER
    assert edition.language == "fr"


def test_persist_import_rejects_missing_existing_work(session: Session) -> None:
    """A missing existing-work target raises a domain-specific exception."""
    request = GoogleBooksImportRequest(
        provider_id="volume-3",
        work_target=ExistingWorkTarget(kind="existing", work_id=uuid4()),
        edition_format=EditionFormat.PAPERBACK,
    )

    with pytest.raises(ImportWorkNotFound), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-3", title="Earthsea", language="en"),
        )

    assert session.scalar(select(func.count()).select_from(Work)) == 0
    assert session.scalar(select(func.count()).select_from(Edition)) == 0


def test_persist_import_creates_work_edition_identifier_and_provenance(
    session: Session,
) -> None:
    """A new target uses the provider title and request work type."""
    request = GoogleBooksImportRequest(
        provider_id="volume-4",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.MANGA),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="volume-4",
                title="  Provider   manga title  ",
                description="  A   manga story. ",
                publisher="  Example   Press ",
                published_date="2001-02-03",
                page_count=240,
                language=" ja ",
                thumbnail_url=" https://books.example/cover.jpg ",
                authors=["  Example   Author "],
                categories=["Ficción & Acción", "Ficción & Acción"],
            ),
        )

    work = session.get(Work, result.work_id)
    edition = session.get(Edition, result.edition_id)
    assert result.work_created is True
    assert result.edition_created is True
    assert work is not None
    assert work.title == "Provider manga title"
    assert work.description == "A manga story."
    assert work.work_type is WorkType.MANGA
    assert edition is not None
    assert edition.work_id == work.id
    assert edition.format is EditionFormat.PAPERBACK
    assert edition.language == "ja"
    assert edition.publisher == "Example Press"
    assert edition.publication_date.isoformat() == "2001-02-03"
    assert edition.page_count == 240
    assert edition.cover_url == "https://books.example/cover.jpg"
    assert [author.name for author in work.authors] == ["Example Author"]
    assert [(genre.name, genre.slug) for genre in work.genres] == [
        ("Ficción & Acción", "ficcion-accion")
    ]
    assert edition.metadata_source is MetadataSource.GOOGLE_BOOKS
    assert edition.metadata_external_id == "volume-4"
    assert edition.metadata_updated_at is not None
    identifier = session.scalar(
        select(EditionExternalIdentifier).where(
            EditionExternalIdentifier.edition_id == edition.id
        )
    )
    assert identifier is not None
    assert identifier.source is ExternalIdentifierSource.GOOGLE_BOOKS
    assert identifier.external_id == "volume-4"


def test_persist_import_uses_language_fallback_when_provider_language_is_absent(
    session: Session,
) -> None:
    """The explicit request fallback supplies the required edition language."""
    work = Work(title="Existing work", work_type=WorkType.BOOK)
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-5",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.EBOOK,
        language_fallback=" pt-BR ",
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-5", title="Earthsea"),
        )

    edition = session.get(Edition, result.edition_id)
    assert edition is not None
    assert edition.language == "pt-BR"


def test_persist_import_requires_language_or_fallback(session: Session) -> None:
    """No edition is created when neither provider language nor fallback exists."""
    work = Work(title="Existing work", work_type=WorkType.BOOK)
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-6",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with pytest.raises(ImportLanguageRequired), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-6", title="Earthsea"),
        )

    assert session.scalar(select(func.count()).select_from(Edition)) == 0


def test_persist_import_requires_edition_format(session: Session) -> None:
    """No edition is created without the requested format."""
    work = Work(title="Existing work", work_type=WorkType.BOOK)
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="volume-7",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        language_fallback="en",
    )

    with pytest.raises(ImportEditionFormatRequired), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id="volume-7", title="Earthsea"),
        )

    assert session.scalar(select(func.count()).select_from(Edition)) == 0


def test_caller_rollback_removes_imported_work_edition_and_identifier(
    session: Session,
) -> None:
    """The service leaves rollback responsibility with its transaction caller."""
    request = GoogleBooksImportRequest(
        provider_id="volume-8",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )

    with pytest.raises(RuntimeError, match="caller rollback"), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="volume-8",
                title="Earthsea",
                language="en",
                isbn_10="0306406152",
                isbn_13="9791090636071",
                publisher="Rollback Press",
                authors=["Rollback Author"],
                categories=["Rollback Genre"],
            ),
        )
        raise RuntimeError("caller rollback")

    assert session.scalar(select(func.count()).select_from(Work)) == 0
    assert session.scalar(select(func.count()).select_from(Edition)) == 0
    assert session.scalar(select(func.count()).select_from(EditionExternalIdentifier)) == 0
    assert session.scalar(select(func.count()).select_from(Author)) == 0
    assert session.scalar(select(func.count()).select_from(Genre)) == 0


@pytest.mark.parametrize("isbn", ["0306406152", "0-306-40615-2"])
def test_isbn_10_validates(isbn: str) -> None:
    assert is_valid_isbn_10(isbn)


def test_isbn_10_accepts_x_check_digit() -> None:
    assert is_valid_isbn_10("0-8044-2957-x")
    assert normalize_isbn_10("0-8044-2957-x") == "080442957X"


@pytest.mark.parametrize("isbn", ["0306406153", "030640615", "0306406152X"])
def test_isbn_10_rejects_bad_checksum_or_length(isbn: str) -> None:
    assert not is_valid_isbn_10(isbn)


@pytest.mark.parametrize("isbn", ["030640615.2", "030640615/2", "٠٣٠٦٤٠٦١٥٢"])
def test_isbn_10_rejects_arbitrary_characters(isbn: str) -> None:
    assert not is_valid_isbn_10(isbn)


@pytest.mark.parametrize("isbn", ["9780306406157", "9791090636071"])
def test_isbn_13_validates_recognized_book_prefixes(isbn: str) -> None:
    assert is_valid_isbn_13(isbn)


@pytest.mark.parametrize(
    "isbn",
    ["9780306406158", "9770306406157", "978030640615", "978/0306406157"],
)
def test_isbn_13_rejects_bad_prefix_checksum_or_length(isbn: str) -> None:
    assert not is_valid_isbn_13(isbn)


def test_isbn_normalization_removes_spaces_and_hyphens() -> None:
    assert normalize_isbn_10("0 306-40615-2") == "0306406152"
    assert normalize_isbn_13("978 0-306-40615-7") == "9780306406157"
    assert normalize_isbn_10("0\u2011306\u201440615\u20152") == "0306406152"
    assert normalize_isbn_13("978\u20110\u2012306\u201440615\u20157") == "9780306406157"
    assert normalize_isbn_10("030640615.2") == "030640615.2"
    assert normalize_isbn_13("978/0306406157") == "978/0306406157"


def test_isbn_10_conversion_returns_equivalent_isbn_13() -> None:
    assert isbn_10_to_13("0-306-40615-2") == "9780306406157"
    assert isbn_10_to_13("0-306-40615-3") is None


def test_persist_import_stores_valid_isbn_10_and_isbn_13(session: Session) -> None:
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-1",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    volume = ExternalBookRead(
        provider_id="isbn-volume-1",
        title="ISBN test",
        language="en",
        isbn_10="0-306-40615-2",
        isbn_13="979-10-90636-07-1",
    )

    with session.begin():
        result = persist_google_books_import(session, request, volume)

    edition = session.get(Edition, result.edition_id)
    assert edition is not None
    assert edition.isbn_10 == "0306406152"
    assert edition.isbn_13 == "9791090636071"
    assert result.warnings == ()


def test_invalid_isbn_is_ignored_with_approved_warning(session: Session) -> None:
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-2",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-volume-2",
                title="ISBN test",
                language="en",
                isbn_10="0306406153",
                isbn_13="9780306406158",
            ),
        )

    edition = session.get(Edition, result.edition_id)
    assert edition is not None
    assert edition.isbn_10 is None
    assert edition.isbn_13 is None
    assert [warning.code for warning in result.warnings] == [
        "isbn_invalid",
        "isbn_invalid",
    ]
    assert all(
        warning.message == "O ISBN informado é inválido e foi ignorado."
        for warning in result.warnings
    )


def test_absent_isbns_do_not_produce_warnings(session: Session) -> None:
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-3",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-volume-3", title="ISBN test", language="en"
            ),
        )

    assert result.warnings == ()


@pytest.mark.parametrize(
    ("stored_field", "incoming_field", "stored_value", "incoming_value"),
    [
        ("isbn_13", "isbn_10", "9780306406157", "0306406152"),
        ("isbn_10", "isbn_13", "0306406152", "9780306406157"),
    ],
)
def test_equivalent_isbn_in_another_edition_is_not_reassigned(
    session: Session,
    stored_field: str,
    incoming_field: str,
    stored_value: str,
    incoming_value: str,
) -> None:
    stored_edition = add_edition(session)
    setattr(stored_edition, stored_field, stored_value)
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-conflict",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    isbn_values = {"isbn_10": None, "isbn_13": None}
    isbn_values[incoming_field] = incoming_value

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-volume-conflict",
                title="Other edition",
                language="en",
                **isbn_values,
            ),
        )

    imported = session.get(Edition, result.edition_id)
    assert imported is not None
    assert imported.isbn_10 is None
    assert imported.isbn_13 is None
    assert [warning.code for warning in result.warnings] == ["isbn_already_assigned"]
    assert result.warnings[0].message == (
        "O ISBN informado já está associado a outra edição e foi ignorado."
    )


def test_equivalent_provider_isbns_emit_one_conflict_warning_and_neither_is_saved(
    session: Session,
) -> None:
    stored_edition = add_edition(session)
    stored_edition.isbn_13 = "9780306406157"
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-both-conflict",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-volume-both-conflict",
                title="Other edition",
                language="en",
                isbn_10="0306406152",
                isbn_13="9780306406157",
            ),
        )

    imported = session.get(Edition, result.edition_id)
    assert imported is not None
    assert imported.isbn_10 is None
    assert imported.isbn_13 is None
    assert [warning.code for warning in result.warnings] == ["isbn_already_assigned"]


def test_conflicting_isbn_does_not_block_persisting_other_isbn(session: Session) -> None:
    stored_edition = add_edition(session)
    stored_edition.isbn_10 = "0306406152"
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-volume-partial-conflict",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-volume-partial-conflict",
                title="Other edition",
                language="en",
                isbn_10="0306406152",
                isbn_13="9791090636071",
            ),
        )

    imported = session.get(Edition, result.edition_id)
    assert imported is not None
    assert imported.isbn_10 is None
    assert imported.isbn_13 == "9791090636071"
    assert [warning.code for warning in result.warnings] == ["isbn_already_assigned"]


def test_existing_edition_preserves_filled_isbn_and_completes_empty_field(
    session: Session,
) -> None:
    edition = add_edition(session, provider_id="isbn-existing-edition")
    edition.isbn_10 = "080442957X"
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-existing-edition",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-existing-edition",
                title="Changed provider title",
                isbn_10="0306406152",
                isbn_13="9791090636071",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.isbn_10 == "080442957X"
    assert stored.isbn_13 == "9791090636071"
    assert result.edition_id == edition_id
    assert result.edition_created is False
    assert result.warnings == ()
    assert session.scalar(select(func.count()).select_from(Edition)) == 1


def test_manual_existing_edition_does_not_change_any_isbn(session: Session) -> None:
    edition = add_edition(session, provider_id="isbn-manual-edition")
    edition.metadata_source = MetadataSource.MANUAL
    edition.isbn_10 = "080442957X"
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-manual-edition",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-manual-edition",
                title="Provider title",
                isbn_10="0306406152",
                isbn_13="9791090636071",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.isbn_10 == "080442957X"
    assert stored.isbn_13 is None
    assert stored.metadata_source is MetadataSource.MANUAL
    assert result.warnings == ()


def test_manual_edition_still_warns_for_invalid_isbn(session: Session) -> None:
    edition = add_edition(session, provider_id="isbn-manual-invalid")
    edition.metadata_source = MetadataSource.MANUAL
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="isbn-manual-invalid",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="isbn-manual-invalid",
                title="Provider title",
                isbn_10="0306406153",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.isbn_10 is None
    assert [warning.code for warning in result.warnings] == ["isbn_invalid"]


def test_fetch_rejects_empty_provider_id_before_calling_provider() -> None:
    provider = FakeBookProvider(result=ExternalBookRead(provider_id="x", title="X"))

    with pytest.raises(ImportProviderIdInvalid):
        asyncio.run(fetch_google_books_volume(provider, " \t "))

    assert provider.requested_ids == []


def test_persist_trims_provider_id_and_rejects_whitespace_only(session: Session) -> None:
    request = GoogleBooksImportRequest(
        provider_id="  trimmed-volume  ",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id=" trimmed-volume ", title="A title", language="en"
            ),
        )
    identifiers = list(session.scalars(select(EditionExternalIdentifier)))
    assert identifiers[0].external_id == "trimmed-volume"
    assert result.edition_id is not None

    invalid_request = GoogleBooksImportRequest(
        provider_id="   ",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    with pytest.raises(ImportProviderIdInvalid):
        persist_google_books_import(
            session,
            invalid_request,
            ExternalBookRead(provider_id=" ", title="A title", language="en"),
        )

    with pytest.raises(ImportProviderIdInvalid):
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(provider_id=" \t ", title="A title", language="en"),
        )

    assert session.scalar(select(func.count()).select_from(Work)) == 1


def test_persist_rejects_mismatched_provider_ids_without_session_changes(
    session: Session,
) -> None:
    request = GoogleBooksImportRequest(
        provider_id="requested-volume",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    volume = ExternalBookRead(
        provider_id="different-volume",
        title="Provider title",
        language="en",
        authors=["Provider Author"],
        categories=["Provider Genre"],
    )

    with pytest.raises(ImportProviderIdMismatch, match="does not match"), session.begin():
        persist_google_books_import(session, request, volume)

    assert not session.new
    assert not session.dirty
    assert not session.deleted
    assert session.scalar(select(func.count()).select_from(Work)) == 0
    assert session.scalar(select(func.count()).select_from(Edition)) == 0
    assert session.scalar(select(func.count()).select_from(Author)) == 0
    assert session.scalar(select(func.count()).select_from(Genre)) == 0
    assert session.scalar(select(func.count()).select_from(EditionExternalIdentifier)) == 0


def test_blank_language_and_fallback_are_rejected_for_new_edition(
    session: Session,
) -> None:
    request = GoogleBooksImportRequest(
        provider_id="blank-language",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
        language_fallback=" \t ",
    )
    with pytest.raises(ImportLanguageRequired), session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="blank-language", title="A title", language="  "
            ),
        )
    assert session.scalar(select(func.count()).select_from(Work)) == 0


@pytest.mark.parametrize(
    ("provider_date", "expected_code"),
    [
        ("2024", "publication_date_incomplete"),
        ("2024-03", "publication_date_incomplete"),
        ("2024-02-30", "publication_date_invalid"),
        ("2024/03/15", "publication_date_invalid"),
    ],
)
def test_incomplete_or_invalid_publication_date_is_ignored_with_warning(
    session: Session, provider_date: str, expected_code: str
) -> None:
    request = GoogleBooksImportRequest(
        provider_id=f"date-{expected_code}-{provider_date}",
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id=request.provider_id,
                title="A title",
                language="en",
                published_date=provider_date,
            ),
        )
    edition = session.get(Edition, result.edition_id)
    assert edition is not None
    assert edition.publication_date is None
    assert [warning.code for warning in result.warnings] == [expected_code]


def test_existing_edition_fills_only_empty_metadata_fields(session: Session) -> None:
    edition = add_edition(session, provider_id="fill-edition")
    edition.publisher = "Existing Publisher"
    edition.page_count = 100
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="fill-edition",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="fill-edition",
                title="Provider title",
                publisher="New Publisher",
                published_date="1998-07-12",
                page_count=250,
                language=" fr ",
                thumbnail_url=" https://books.example/new-cover.jpg ",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.publisher == "Existing Publisher"
    assert stored.page_count == 100
    assert stored.publication_date.isoformat() == "1998-07-12"
    assert stored.language == "en"
    assert stored.cover_url == "https://books.example/new-cover.jpg"
    assert result.warnings == ()


def test_existing_work_with_empty_description_does_not_receive_provider_description(
    session: Session,
) -> None:
    work = Work(title="Existing title", work_type=WorkType.BOOK, description=None)
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="existing-work-description",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="existing-work-description",
                title="Provider title",
                description="Provider description",
                language="en",
            ),
        )

    stored_work = session.get(Work, work_id)
    assert stored_work is not None
    assert stored_work.title == "Existing title"
    assert stored_work.description is None
    assert result.work_created is False


def test_manual_edition_preserves_all_edition_metadata_and_provenance(
    session: Session,
) -> None:
    edition = add_edition(session, provider_id="manual-all-metadata")
    timestamp = datetime(2020, 1, 2, tzinfo=UTC)
    edition.metadata_source = MetadataSource.MANUAL
    edition.metadata_external_id = "manual-entry"
    edition.metadata_updated_at = timestamp
    edition.isbn_10 = "080442957X"
    edition.publisher = "Manual Publisher"
    edition.page_count = 88
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="manual-all-metadata",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="manual-all-metadata",
                title="Provider title",
                description="Provider description",
                isbn_10="0306406152",
                isbn_13="9791090636071",
                publisher="Provider Publisher",
                published_date="2000-01-01",
                page_count=200,
                language="fr",
                thumbnail_url="https://books.example/provider.jpg",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.metadata_source is MetadataSource.MANUAL
    assert stored.metadata_external_id == "manual-entry"
    assert stored.metadata_updated_at == timestamp.replace(tzinfo=None)
    assert stored.isbn_10 == "080442957X"
    assert stored.isbn_13 is None
    assert stored.publisher == "Manual Publisher"
    assert stored.publication_date is None
    assert stored.page_count == 88
    assert stored.language == "en"
    assert stored.cover_url is None
    assert result.warnings == ()


def test_missing_provenance_is_completed_only_when_edition_metadata_changes(
    session: Session,
) -> None:
    edition = add_edition(session, provider_id="missing-provenance")
    edition.metadata_source = None
    edition.metadata_external_id = "keep-existing-id"
    original_timestamp = datetime(2019, 4, 5, tzinfo=UTC)
    edition.metadata_updated_at = original_timestamp
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="missing-provenance",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )
    import_started_at = datetime.now(UTC).replace(tzinfo=None)

    with session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="missing-provenance",
                title="Provider title",
                publisher="Imported Publisher",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.publisher == "Imported Publisher"
    assert stored.metadata_source is MetadataSource.GOOGLE_BOOKS
    assert stored.metadata_external_id == "missing-provenance"
    assert stored.metadata_updated_at is not None
    assert stored.metadata_updated_at != original_timestamp.replace(tzinfo=None)
    assert import_started_at <= stored.metadata_updated_at <= datetime.now(UTC).replace(
        tzinfo=None
    )


def test_missing_provenance_is_not_added_without_effective_edition_metadata(
    session: Session,
) -> None:
    edition = add_edition(session, provider_id="no-metadata-provenance")
    edition.metadata_source = None
    edition.metadata_external_id = None
    edition.metadata_updated_at = None
    edition.publisher = "Already filled"
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="no-metadata-provenance",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="no-metadata-provenance", title="Provider title"
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.metadata_source is None
    assert stored.metadata_external_id is None
    assert stored.metadata_updated_at is None


def test_existing_nonmanual_provenance_is_preserved(session: Session) -> None:
    edition = add_edition(session, provider_id="other-provenance")
    timestamp = datetime(2018, 8, 9, tzinfo=UTC)
    edition.metadata_source = MetadataSource.OPEN_LIBRARY
    edition.metadata_external_id = "open-library-id"
    edition.metadata_updated_at = timestamp
    edition_id = edition.id
    work_id = edition.work_id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="other-provenance",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
    )

    with session.begin():
        persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="other-provenance",
                title="Provider title",
                publisher="New Publisher",
            ),
        )

    stored = session.get(Edition, edition_id)
    assert stored is not None
    assert stored.metadata_source is MetadataSource.OPEN_LIBRARY
    assert stored.metadata_external_id == "open-library-id"
    assert stored.metadata_updated_at == timestamp.replace(tzinfo=None)


def test_existing_authors_and_genres_are_reused_additively_without_duplicates(
    session: Session,
) -> None:
    work = Work(title="Existing work", work_type=WorkType.BOOK)
    original_author = Author(name="Original Author")
    existing_author = Author(name="Jane   Doe")
    original_genre = Genre(name="Classic", slug="classic")
    existing_genre = Genre(name="Mystery", slug="mystery")
    work.authors.extend([original_author, existing_author])
    work.genres.extend([original_genre, existing_genre])
    session.add(work)
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="additive-relations",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="additive-relations",
                title="Provider title",
                language="en",
                authors=[" jane doe ", "New Author", "New   Author"],
                categories=[" mystery ", "New Genre", "New   Genre"],
            ),
        )

    stored_work = session.get(Work, work_id)
    assert stored_work is not None
    assert {author.name for author in stored_work.authors} == {
        "Original Author",
        "Jane   Doe",
        "New Author",
    }
    assert {genre.name for genre in stored_work.genres} == {
        "Classic",
        "Mystery",
        "New Genre",
    }
    assert session.scalar(select(func.count()).select_from(Author)) == 3
    assert session.scalar(select(func.count()).select_from(Genre)) == 3
    assert result.warnings == ()


def test_ambiguous_author_is_not_created_or_associated_and_warning_is_deduplicated(
    session: Session,
) -> None:
    work = Work(title="Ambiguous author work", work_type=WorkType.BOOK)
    session.add_all([Author(name="Alex Smith"), Author(name=" alex   smith "), work])
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="ambiguous-author",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="ambiguous-author",
                title="Provider title",
                language="en",
                authors=[" Alex Smith ", "alex   smith"],
            ),
        )

    stored_work = session.get(Work, work_id)
    assert stored_work is not None
    assert stored_work.authors == []
    assert session.scalar(select(func.count()).select_from(Author)) == 2
    assert [warning.code for warning in result.warnings] == ["author_ambiguous"]


def test_ambiguous_genre_is_not_created_or_associated(session: Session) -> None:
    work = Work(title="Ambiguous genre work", work_type=WorkType.BOOK)
    session.add_all(
        [
            Genre(name="Mystery", slug="mystery-one"),
            Genre(name=" mystery ", slug="mystery-two"),
            work,
        ]
    )
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="ambiguous-genre",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="ambiguous-genre",
                title="Provider title",
                language="en",
                categories=["Mystery", " mystery "],
            ),
        )

    stored_work = session.get(Work, work_id)
    assert stored_work is not None
    assert stored_work.genres == []
    assert session.scalar(select(func.count()).select_from(Genre)) == 2
    assert [warning.code for warning in result.warnings] == ["genre_ambiguous"]


def test_genre_slug_collision_does_not_associate_different_genre(session: Session) -> None:
    work = Work(title="Slug collision work", work_type=WorkType.BOOK)
    session.add_all([Genre(name="Sci-Fi", slug="sci-fi"), work])
    session.flush()
    work_id = work.id
    session.commit()
    request = GoogleBooksImportRequest(
        provider_id="genre-slug-collision",
        work_target=ExistingWorkTarget(kind="existing", work_id=work_id),
        edition_format=EditionFormat.PAPERBACK,
    )

    with session.begin():
        result = persist_google_books_import(
            session,
            request,
            ExternalBookRead(
                provider_id="genre-slug-collision",
                title="Provider title",
                language="en",
                categories=["Sci Fi", "Sci Fi"],
            ),
        )

    stored_work = session.get(Work, work_id)
    assert stored_work is not None
    assert stored_work.genres == []
    assert session.scalar(select(func.count()).select_from(Genre)) == 1
    assert [warning.code for warning in result.warnings] == ["genre_slug_collision"]


def test_reimport_reuses_edition_and_does_not_duplicate_authors_or_genres(
    session: Session,
) -> None:
    provider_id = "idempotent-with-relations"
    volume = ExternalBookRead(
        provider_id=provider_id,
        title="Idempotent title",
        description="Description",
        language="en",
        authors=["Author One"],
        categories=["Science Fiction"],
    )
    new_request = GoogleBooksImportRequest(
        provider_id=provider_id,
        work_target=NewWorkTarget(kind="new", work_type=WorkType.BOOK),
        edition_format=EditionFormat.PAPERBACK,
    )
    with session.begin():
        first_result = persist_google_books_import(session, new_request, volume)

    existing_request = GoogleBooksImportRequest(
        provider_id=provider_id,
        work_target=ExistingWorkTarget(kind="existing", work_id=first_result.work_id),
    )
    with session.begin():
        second_result = persist_google_books_import(
            session, existing_request, volume
        )

    work = session.get(Work, first_result.work_id)
    assert work is not None
    assert second_result.work_id == first_result.work_id
    assert second_result.edition_id == first_result.edition_id
    assert second_result.work_created is False
    assert second_result.edition_created is False
    assert len(work.authors) == 1
    assert len(work.genres) == 1
    assert session.scalar(select(func.count()).select_from(Work)) == 1
    assert session.scalar(select(func.count()).select_from(Edition)) == 1
    assert session.scalar(select(func.count()).select_from(Author)) == 1
    assert session.scalar(select(func.count()).select_from(Genre)) == 1
