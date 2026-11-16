"""Persistence tests for external identifiers attached to editions."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models import (
    Edition,
    EditionExternalIdentifier,
    EditionFormat,
    ExternalIdentifierSource,
    Work,
    WorkType,
)


@pytest.fixture
def session() -> Iterator[Session]:
    """Create an isolated SQLite database with foreign-key enforcement enabled."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection: object, connection_record: object
    ) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        yield db
    engine.dispose()


def _edition(session: Session) -> Edition:
    """Add and return the minimum valid edition needed by these tests."""
    work = Work(title="Example", work_type=WorkType.BOOK)
    edition = Edition(work=work, language="en", format=EditionFormat.PAPERBACK)
    session.add(edition)
    session.flush()
    return edition


def test_external_identifier_is_related_to_edition(session: Session) -> None:
    edition = _edition(session)
    identifier = EditionExternalIdentifier(
        edition=edition,
        source=ExternalIdentifierSource.GOOGLE_BOOKS,
        external_id="google-volume-1",
    )
    session.add(identifier)
    session.commit()

    stored = session.scalar(select(EditionExternalIdentifier))
    assert stored is not None
    assert stored.edition_id == edition.id
    assert stored.edition is edition
    assert edition.external_identifiers == [stored]
    assert stored.id is not None
    assert stored.created_at is not None


def test_edition_can_have_identifiers_from_multiple_providers(session: Session) -> None:
    edition = _edition(session)
    session.add_all(
        [
            EditionExternalIdentifier(
                edition=edition,
                source=ExternalIdentifierSource.GOOGLE_BOOKS,
                external_id="same-id",
            ),
            EditionExternalIdentifier(
                edition=edition,
                source=ExternalIdentifierSource.OPEN_LIBRARY,
                external_id="same-id",
            ),
        ]
    )

    session.commit()

    assert len(edition.external_identifiers) == 2


def test_duplicate_source_and_external_id_is_rejected(session: Session) -> None:
    edition = _edition(session)
    other_edition = _edition(session)
    session.add(
        EditionExternalIdentifier(
            edition=other_edition,
            source=ExternalIdentifierSource.GOOGLE_BOOKS,
            external_id="duplicate-id",
        )
    )
    session.commit()
    session.add(
        EditionExternalIdentifier(
            edition=edition,
            source=ExternalIdentifierSource.GOOGLE_BOOKS,
            external_id="duplicate-id",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_same_external_id_is_allowed_for_different_providers(session: Session) -> None:
    edition = _edition(session)
    other_edition = _edition(session)
    session.add_all(
        [
            EditionExternalIdentifier(
                edition=edition,
                source=ExternalIdentifierSource.GOOGLE_BOOKS,
                external_id="shared-id",
            ),
            EditionExternalIdentifier(
                edition=other_edition,
                source=ExternalIdentifierSource.OPEN_LIBRARY,
                external_id="shared-id",
            ),
        ]
    )

    session.commit()

    assert (
        session.scalar(
            select(EditionExternalIdentifier).where(
                EditionExternalIdentifier.external_id == "shared-id"
            )
        )
        is not None
    )


def test_deleting_edition_cascades_to_external_identifiers(session: Session) -> None:
    edition = _edition(session)
    session.add(
        EditionExternalIdentifier(
            edition=edition,
            source=ExternalIdentifierSource.GOOGLE_BOOKS,
            external_id="cascade-id",
        )
    )
    session.commit()

    session.execute(delete(Edition).where(Edition.id == edition.id))
    session.commit()

    assert session.scalar(select(EditionExternalIdentifier.id)) is None


@pytest.mark.parametrize(
    "source,external_id",
    [
        (None, "present-id"),
        (ExternalIdentifierSource.GOOGLE_BOOKS, None),
    ],
)
def test_source_and_external_id_are_required(
    session: Session,
    source: ExternalIdentifierSource | None,
    external_id: str | None,
) -> None:
    edition = _edition(session)
    session.add(
        EditionExternalIdentifier(
            edition=edition,
            source=source,
            external_id=external_id,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_identifier_requires_an_existing_edition(session: Session) -> None:
    session.add(
        EditionExternalIdentifier(
            edition_id=uuid.uuid4(),
            source=ExternalIdentifierSource.GOOGLE_BOOKS,
            external_id="orphan-id",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
