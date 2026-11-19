"""Application helpers for the Google Books catalog import flow."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Author,
    Edition,
    EditionExternalIdentifier,
    ExternalIdentifierSource,
    Genre,
    MetadataSource,
    Work,
)
from app.schemas.catalog_imports import (
    ExistingWorkTarget,
    GoogleBooksImportRequest,
    GoogleBooksImportWarning,
    NewWorkTarget,
    WarningCode,
    WorkTarget,
)
from app.schemas.external_books import ExternalBookRead
from app.services.external_books.base import BookProvider


class GoogleBooksVolumeNotFound(Exception):
    """The requested volume does not exist in Google Books."""


class ImportDestinationConflict(Exception):
    """The requested work destination conflicts with an existing edition."""


class ImportWorkNotFound(Exception):
    """The requested existing work does not exist in the catalog."""


class ImportEditionFormatRequired(Exception):
    """An edition format is required when creating an edition."""


class ImportLanguageRequired(Exception):
    """A provider language or explicit fallback is required for an edition."""


class ImportProviderIdInvalid(Exception):
    """The Google Books provider identifier is empty or whitespace-only."""


class ImportProviderIdMismatch(Exception):
    """The request ID does not identify the supplied Google Books volume."""


@dataclass(frozen=True, slots=True)
class ExistingEditionMatch:
    """Identifiers needed after resolving an edition in the current session."""

    edition_id: UUID
    work_id: UUID


@dataclass(frozen=True, slots=True)
class GoogleBooksImportResult:
    """Immutable identifiers and creation flags for an import operation."""

    work_id: UUID
    edition_id: UUID
    work_created: bool
    edition_created: bool
    warnings: tuple[GoogleBooksImportWarning, ...] = ()


def normalize_isbn_10(value: str) -> str:
    """Remove ISBN-10 formatting separators and uppercase its X check digit."""
    return re.sub(r"[\s\-\u2010-\u2015\u2212]", "", value).upper()


def is_valid_isbn_10(value: str) -> bool:
    """Validate ISBN-10 shape and its modulo-11 checksum."""
    normalized = normalize_isbn_10(value)
    if re.fullmatch(r"[0-9]{9}[0-9X]", normalized) is None:
        return False
    checksum = sum(
        (10 - index) * (10 if character == "X" else int(character))
        for index, character in enumerate(normalized)
    )
    return checksum % 11 == 0


def normalize_isbn_13(value: str) -> str:
    """Remove ISBN-13 formatting separators."""
    return re.sub(r"[\s\-\u2010-\u2015\u2212]", "", value)


def is_valid_isbn_13(value: str) -> bool:
    """Validate ISBN-13 shape, book prefix, and modulo-10 checksum."""
    normalized = normalize_isbn_13(value)
    if re.fullmatch(r"[0-9]{13}", normalized) is None:
        return False
    if not normalized.startswith(("978", "979")):
        return False
    checksum = sum(
        int(character) * (1 if index % 2 == 0 else 3)
        for index, character in enumerate(normalized[:12])
    )
    expected_check_digit = (-checksum) % 10
    return expected_check_digit == int(normalized[12])


def isbn_10_to_13(value: str) -> str | None:
    """Convert a valid ISBN-10 to its equivalent 978-prefixed ISBN-13."""
    normalized = normalize_isbn_10(value)
    if not is_valid_isbn_10(normalized):
        return None
    first_twelve = f"978{normalized[:9]}"
    checksum = sum(
        int(character) * (1 if index % 2 == 0 else 3)
        for index, character in enumerate(first_twelve)
    )
    return f"{first_twelve}{(-checksum) % 10}"


def _isbn_identity(value: str, *, isbn_10: bool) -> str | None:
    """Return the canonical ISBN-13 identity for a valid ISBN value."""
    if isbn_10:
        return isbn_10_to_13(value)
    normalized = normalize_isbn_13(value)
    return normalized if is_valid_isbn_13(normalized) else None


def _warning(code: WarningCode, message: str) -> GoogleBooksImportWarning:
    return GoogleBooksImportWarning(code=code, message=message)


def _persist_isbns(
    session: Session,
    edition: Edition,
    volume: ExternalBookRead,
    *,
    protect_manual_metadata: bool,
) -> tuple[GoogleBooksImportWarning, ...]:
    """Validate provider ISBNs, warn on conflicts, and fill eligible empty fields."""
    warnings: list[GoogleBooksImportWarning] = []
    emitted_warning_keys: set[tuple[str, str]] = set()

    def add_warning(code: WarningCode, message: str, identity: str) -> None:
        key = (code, identity)
        if key not in emitted_warning_keys:
            emitted_warning_keys.add(key)
            warnings.append(_warning(code, message))

    candidates: list[tuple[str, str, str]] = []
    for field, raw_value, is_isbn_10 in (
        ("isbn_10", volume.isbn_10, True),
        ("isbn_13", volume.isbn_13, False),
    ):
        if raw_value is None:
            continue
        normalized = (
            normalize_isbn_10(raw_value)
            if is_isbn_10
            else normalize_isbn_13(raw_value)
        )
        valid = is_valid_isbn_10(normalized) if is_isbn_10 else is_valid_isbn_13(normalized)
        if not valid:
            add_warning(
                "isbn_invalid",
                "O ISBN informado é inválido e foi ignorado.",
                normalized,
            )
            continue
        identity = _isbn_identity(normalized, isbn_10=is_isbn_10)
        if identity is not None:
            candidates.append((field, normalized, identity))

    if not candidates:
        return tuple(warnings)

    # Compare normalized identities in Python so legacy values are never rewritten
    # and cross-format ISBN-10/ISBN-13 assignments are detected.
    stored_isbns = session.execute(
        select(Edition.id, Edition.isbn_10, Edition.isbn_13).where(
            or_(Edition.isbn_10.is_not(None), Edition.isbn_13.is_not(None))
        )
    ).all()
    identities_by_edition: dict[UUID, set[str]] = {}
    for edition_id, stored_isbn_10, stored_isbn_13 in stored_isbns:
        identities = identities_by_edition.setdefault(edition_id, set())
        if stored_isbn_10 is not None:
            identity = _isbn_identity(stored_isbn_10, isbn_10=True)
            if identity is not None:
                identities.add(identity)
        if stored_isbn_13 is not None:
            identity = _isbn_identity(stored_isbn_13, isbn_10=False)
            if identity is not None:
                identities.add(identity)

    for field, value, identity in candidates:
        conflict = any(
            other_edition_id != edition.id and identity in identities
            for other_edition_id, identities in identities_by_edition.items()
        )
        if conflict:
            add_warning(
                "isbn_already_assigned",
                "O ISBN informado já está associado a outra edição e foi ignorado.",
                identity,
            )
            continue
        if protect_manual_metadata:
            continue
        if getattr(edition, field) is None:
            setattr(edition, field, value)
            identities_by_edition.setdefault(edition.id, set()).add(identity)

    return tuple(warnings)


def _normalize_text(value: str | None) -> str | None:
    """Trim text and collapse internal whitespace, treating blanks as absent."""
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _normalize_provider_id(value: str) -> str:
    """Trim a provider ID and reject values containing only whitespace."""
    normalized = value.strip()
    if not normalized:
        raise ImportProviderIdInvalid("The Google Books provider ID cannot be empty.")
    return normalized


def _parse_publication_date(
    value: str | None,
) -> tuple[date | None, GoogleBooksImportWarning | None]:
    """Parse complete ISO publication dates and classify partial or invalid input."""
    normalized = _normalize_text(value)
    if normalized is None:
        return None, None
    if re.fullmatch(r"[0-9]{4}(?:-[0-9]{2})?", normalized):
        return None, _warning(
            "publication_date_incomplete",
            "A data de publicação está incompleta e foi ignorada.",
        )
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", normalized) is None:
        return None, _warning(
            "publication_date_invalid",
            "A data de publicação é inválida e foi ignorada.",
        )
    try:
        return date.fromisoformat(normalized), None
    except ValueError:
        return None, _warning(
            "publication_date_invalid",
            "A data de publicação é inválida e foi ignorada.",
        )


def _append_author_once(work: Work, author: Author) -> None:
    """Add an author relationship only if this Work does not already have it."""
    if not any(
        existing is author
        or (author.id is not None and existing.id == author.id)
        for existing in work.authors
    ):
        work.authors.append(author)


def _resolve_authors(
    session: Session, work: Work, names: list[str]
) -> tuple[GoogleBooksImportWarning, ...]:
    """Resolve provider author names and add unambiguous Work relationships."""
    authors = list(session.scalars(select(Author)))
    by_name: dict[str, list[Author]] = {}
    for author in authors:
        normalized = _normalize_text(author.name)
        if normalized is not None:
            by_name.setdefault(normalized.casefold(), []).append(author)

    warnings: list[GoogleBooksImportWarning] = []
    processed_names: set[str] = set()
    for raw_name in names:
        name = _normalize_text(raw_name)
        if name is None:
            continue
        key = name.casefold()
        if key in processed_names:
            continue
        processed_names.add(key)

        matches = by_name.get(key, [])
        if len(matches) > 1:
            warnings.append(
                _warning(
                    "author_ambiguous",
                    "O autor informado corresponde a mais de um cadastro e não foi associado.",
                )
            )
            continue
        if matches:
            author = matches[0]
        else:
            author = Author(name=name)
            session.add(author)
            by_name.setdefault(key, []).append(author)
        _append_author_once(work, author)

    return tuple(warnings)


def _genre_slug(name: str) -> str:
    """Build a deterministic lowercase slug while removing combining accents."""
    decomposed = unicodedata.normalize("NFKD", name)
    unaccented = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    slug = re.sub(r"[\W_]+", "-", unaccented.casefold()).strip("-")
    return re.sub(r"-+", "-", slug)


def _append_genre_once(work: Work, genre: Genre) -> None:
    """Add a genre relationship only if this Work does not already have it."""
    if not any(
        existing is genre
        or (genre.id is not None and existing.id == genre.id)
        for existing in work.genres
    ):
        work.genres.append(genre)


def _resolve_genres(
    session: Session, work: Work, categories: list[str]
) -> tuple[GoogleBooksImportWarning, ...]:
    """Resolve genre categories by normalized name and detect slug collisions."""
    genres = list(session.scalars(select(Genre)))
    warnings: list[GoogleBooksImportWarning] = []
    processed_names: set[str] = set()

    for raw_name in categories:
        name = _normalize_text(raw_name)
        if name is None:
            continue
        key = name.casefold()
        if key in processed_names:
            continue
        processed_names.add(key)

        matches = [
            genre
            for genre in genres
            if (normalized := _normalize_text(genre.name)) is not None
            and normalized.casefold() == key
        ]
        if len(matches) > 1:
            warnings.append(
                _warning(
                    "genre_ambiguous",
                    "A categoria informada corresponde a mais de um gênero e não foi associada.",
                )
            )
            continue
        if matches:
            _append_genre_once(work, matches[0])
            continue

        slug = _genre_slug(name)
        if not slug:
            continue
        slug_owner = next(
            (genre for genre in genres if genre.slug.casefold() == slug), None
        )
        if slug_owner is not None:
            warnings.append(
                _warning(
                    "genre_slug_collision",
                    "O slug da categoria já pertence a outro gênero e a associação foi ignorada.",
                )
            )
            continue

        genre = Genre(name=name, slug=slug)
        session.add(genre)
        genres.append(genre)
        _append_genre_once(work, genre)

    return tuple(warnings)


def _edition_metadata_snapshot(edition: Edition) -> tuple[object, ...]:
    """Capture imported Edition fields to detect effective metadata changes."""
    return (
        edition.isbn_10,
        edition.isbn_13,
        edition.publisher,
        edition.publication_date,
        edition.page_count,
        edition.language,
        edition.cover_url,
    )


def _fill_edition_metadata(
    edition: Edition,
    volume: ExternalBookRead,
    language: str | None,
) -> tuple[GoogleBooksImportWarning, ...]:
    """Fill empty Edition metadata fields and report malformed publication dates."""
    warnings: list[GoogleBooksImportWarning] = []
    publisher = _normalize_text(volume.publisher)
    thumbnail_url = volume.thumbnail_url.strip() if volume.thumbnail_url else None
    publication_date, date_warning = _parse_publication_date(volume.published_date)
    if date_warning is not None:
        warnings.append(date_warning)

    if (edition.publisher is None or not edition.publisher.strip()) and publisher is not None:
        edition.publisher = publisher
    if edition.publication_date is None and publication_date is not None:
        edition.publication_date = publication_date
    if edition.page_count is None and volume.page_count is not None:
        edition.page_count = volume.page_count
    if (edition.language is None or not edition.language.strip()) and language is not None:
        edition.language = language
    if (edition.cover_url is None or not edition.cover_url.strip()) and thumbnail_url:
        edition.cover_url = thumbnail_url

    return tuple(warnings)


async def fetch_google_books_volume(
    provider: BookProvider, provider_id: str
) -> ExternalBookRead:
    """Fetch one normalized volume without opening or using a database session."""
    normalized_provider_id = _normalize_provider_id(provider_id)
    volume = await provider.get_by_id(normalized_provider_id)
    if volume is None:
        raise GoogleBooksVolumeNotFound(provider_id)
    return volume


def find_edition_by_google_books_id(
    session: Session, provider_id: str
) -> ExistingEditionMatch | None:
    """Find an edition by its Google Books identifier without changing records."""
    statement = (
        select(Edition)
        .join(
            EditionExternalIdentifier,
            EditionExternalIdentifier.edition_id == Edition.id,
        )
        .where(
            EditionExternalIdentifier.source
            == ExternalIdentifierSource.GOOGLE_BOOKS,
            EditionExternalIdentifier.external_id == provider_id,
        )
    )
    edition = session.scalar(statement)
    if edition is None:
        return None
    return ExistingEditionMatch(edition_id=edition.id, work_id=edition.work_id)


def ensure_work_target_compatible(
    work_target: WorkTarget, edition: ExistingEditionMatch
) -> None:
    """Raise a domain conflict unless the target names the edition's work."""
    if isinstance(work_target, ExistingWorkTarget) and work_target.work_id == edition.work_id:
        return
    if isinstance(work_target, NewWorkTarget):
        raise ImportDestinationConflict(
            "An edition already belongs to an existing work."
        )
    raise ImportDestinationConflict(
        "The requested work does not match the edition's existing work."
    )


def persist_google_books_import(
    session: Session,
    request: GoogleBooksImportRequest,
    volume: ExternalBookRead,
) -> GoogleBooksImportResult:
    """Persist the initial import using the caller's transaction and session.

    The caller must invoke this function inside a transaction and roll back that
    transaction if this function raises. This function never opens, commits,
    rolls back, or closes the supplied session.
    """
    provider_id = _normalize_provider_id(request.provider_id)
    volume_provider_id = _normalize_provider_id(volume.provider_id)
    if provider_id != volume_provider_id:
        raise ImportProviderIdMismatch(
            "The request provider ID does not match the supplied Google Books volume."
        )
    language = _normalize_text(volume.language) or _normalize_text(
        request.language_fallback
    )
    existing_edition = find_edition_by_google_books_id(session, provider_id)
    if existing_edition is not None:
        ensure_work_target_compatible(request.work_target, existing_edition)
        edition = session.get(Edition, existing_edition.edition_id)
        if edition is None:
            raise RuntimeError("Resolved edition disappeared in the active session.")
        work = session.get(Work, existing_edition.work_id)
        if work is None:
            raise ImportWorkNotFound(existing_edition.work_id)

        warnings: list[GoogleBooksImportWarning] = []
        before_metadata = _edition_metadata_snapshot(edition)
        is_manual = edition.metadata_source is MetadataSource.MANUAL
        if is_manual:
            _, date_warning = _parse_publication_date(volume.published_date)
            if date_warning is not None:
                warnings.append(date_warning)
        else:
            warnings.extend(_fill_edition_metadata(edition, volume, language))
        warnings.extend(
            _persist_isbns(
                session,
                edition,
                volume,
                protect_manual_metadata=is_manual,
            )
        )
        warnings.extend(_resolve_authors(session, work, volume.authors))
        warnings.extend(_resolve_genres(session, work, volume.categories))

        if (
            not is_manual
            and _edition_metadata_snapshot(edition) != before_metadata
            and edition.metadata_source is None
        ):
            edition.metadata_source = MetadataSource.GOOGLE_BOOKS
            edition.metadata_external_id = provider_id
            edition.metadata_updated_at = datetime.now(UTC)

        session.flush()
        return GoogleBooksImportResult(
            work_id=existing_edition.work_id,
            edition_id=existing_edition.edition_id,
            work_created=False,
            edition_created=False,
            warnings=tuple(warnings),
        )

    if request.edition_format is None:
        raise ImportEditionFormatRequired

    if language is None:
        raise ImportLanguageRequired

    work_created = isinstance(request.work_target, NewWorkTarget)
    if isinstance(request.work_target, ExistingWorkTarget):
        work = session.get(Work, request.work_target.work_id)
        if work is None:
            raise ImportWorkNotFound(request.work_target.work_id)
    else:
        work = Work(
            title=_normalize_text(volume.title) or "",
            description=_normalize_text(volume.description),
            work_type=request.work_target.work_type,
        )
        session.add(work)

    publication_date, date_warning = _parse_publication_date(volume.published_date)
    warnings = [date_warning] if date_warning is not None else []
    edition = Edition(
        work=work,
        format=request.edition_format,
        language=language,
        publisher=_normalize_text(volume.publisher),
        publication_date=publication_date,
        page_count=volume.page_count,
        cover_url=(volume.thumbnail_url.strip() or None)
        if volume.thumbnail_url
        else None,
        metadata_source=MetadataSource.GOOGLE_BOOKS,
        metadata_external_id=provider_id,
        metadata_updated_at=datetime.now(UTC),
    )
    edition.external_identifiers.append(
        EditionExternalIdentifier(
            source=ExternalIdentifierSource.GOOGLE_BOOKS,
            external_id=provider_id,
        )
    )
    session.add(edition)
    warnings.extend(
        _persist_isbns(session, edition, volume, protect_manual_metadata=False)
    )
    warnings.extend(_resolve_authors(session, work, volume.authors))
    warnings.extend(_resolve_genres(session, work, volume.categories))
    session.flush()

    return GoogleBooksImportResult(
        work_id=work.id,
        edition_id=edition.id,
        work_created=work_created,
        edition_created=True,
        warnings=tuple(warnings),
    )
