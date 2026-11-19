"""Tests for Google Books catalog import request and response schemas."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import EditionFormat, WorkType
from app.schemas.catalog_imports import (
    ExistingWorkTarget,
    GoogleBooksImportRequest,
    GoogleBooksImportResponse,
    GoogleBooksImportWarning,
    NewWorkTarget,
)


def test_import_request_accepts_existing_work_target() -> None:
    """Existing target parses its discriminator and UUID field."""
    work_id = uuid4()

    request = GoogleBooksImportRequest.model_validate(
        {
            "provider_id": "google-volume-1",
            "work_target": {"kind": "existing", "work_id": str(work_id)},
        }
    )

    assert isinstance(request.work_target, ExistingWorkTarget)
    assert request.work_target.kind == "existing"
    assert request.work_target.work_id == work_id
    assert request.edition_format is None
    assert request.language_fallback is None


def test_import_request_accepts_new_work_target_and_existing_enums() -> None:
    """New target uses the WorkType enum and optional edition format enum."""
    request = GoogleBooksImportRequest(
        provider_id="google-volume-2",
        work_target={"kind": "new", "work_type": "manga"},
        edition_format="paperback",
        language_fallback="pt-BR",
    )

    assert isinstance(request.work_target, NewWorkTarget)
    assert request.work_target.work_type is WorkType.MANGA
    assert request.edition_format is EditionFormat.PAPERBACK
    assert request.language_fallback == "pt-BR"


def test_import_request_rejects_unknown_work_target_kind() -> None:
    """The discriminated union rejects unrecognized variants."""
    with pytest.raises(ValidationError):
        GoogleBooksImportRequest.model_validate(
            {
                "provider_id": "google-volume-1",
                "work_target": {"kind": "other", "work_id": str(uuid4())},
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"work_target": {"kind": "new", "work_type": "book"}},
        {"provider_id": "google-volume-1"},
        {"provider_id": "google-volume-1", "work_target": {"kind": "existing"}},
        {"provider_id": "google-volume-1", "work_target": {"kind": "new"}},
        {"provider_id": "google-volume-1", "work_target": {"work_id": str(uuid4())}},
    ],
)
def test_import_request_rejects_missing_required_fields(
    payload: dict[str, object],
) -> None:
    """Required request and selected target fields cannot be omitted."""
    with pytest.raises(ValidationError):
        GoogleBooksImportRequest.model_validate(payload)


@pytest.mark.parametrize("work_id", ["not-a-uuid", 123])
def test_existing_work_target_validates_uuid(work_id: object) -> None:
    """Existing work identifiers must parse as UUID values."""
    with pytest.raises(ValidationError):
        GoogleBooksImportRequest.model_validate(
            {
                "provider_id": "google-volume-1",
                "work_target": {"kind": "existing", "work_id": work_id},
            }
        )


@pytest.mark.parametrize(
    "code",
    [
        "isbn_invalid",
        "isbn_already_assigned",
        "publication_date_incomplete",
        "publication_date_invalid",
        "author_ambiguous",
        "genre_ambiguous",
        "genre_slug_collision",
    ],
)
def test_import_warning_accepts_approved_code(code: str) -> None:
    """Every warning code approved for the MVP is represented in the schema."""
    warning = GoogleBooksImportWarning(code=code, message="Readable warning")

    assert warning.code == code
    assert warning.message == "Readable warning"


def test_import_warning_rejects_unknown_code() -> None:
    """Warning codes outside the approved contract are rejected."""
    with pytest.raises(ValidationError):
        GoogleBooksImportWarning(code="unknown_warning", message="Warning")


def test_import_response_serializes_empty_warning_list() -> None:
    """Response UUIDs serialize as strings and warnings default to an empty list."""
    work_id = uuid4()
    edition_id = uuid4()
    response = GoogleBooksImportResponse(
        work_id=work_id,
        edition_id=edition_id,
        work_created=False,
        edition_created=False,
    )

    assert response.warnings == []
    assert response.model_dump(mode="json") == {
        "work_id": str(work_id),
        "edition_id": str(edition_id),
        "work_created": False,
        "edition_created": False,
        "warnings": [],
    }


def test_import_response_serializes_warnings() -> None:
    """Response serializes warning codes and messages with import identifiers."""
    work_id = UUID("00000000-0000-0000-0000-000000000001")
    edition_id = UUID("00000000-0000-0000-0000-000000000002")
    response = GoogleBooksImportResponse(
        work_id=work_id,
        edition_id=edition_id,
        work_created=True,
        edition_created=True,
        warnings=[
            GoogleBooksImportWarning(
                code="isbn_invalid", message="ISBN ignored because it is invalid."
            )
        ],
    )

    assert response.model_dump(mode="json") == {
        "work_id": str(work_id),
        "edition_id": str(edition_id),
        "work_created": True,
        "edition_created": True,
        "warnings": [
            {
                "code": "isbn_invalid",
                "message": "ISBN ignored because it is invalid.",
            }
        ],
    }


@pytest.mark.parametrize("field", ["title", "publisher", "authors", "isbn_13"])
def test_import_request_rejects_provider_metadata(field: str) -> None:
    """Editorial metadata is not accepted as client-supplied request fields."""
    with pytest.raises(ValidationError):
        GoogleBooksImportRequest.model_validate(
            {
                "provider_id": "google-volume-1",
                "work_target": {"kind": "new", "work_type": "book"},
                field: "client-provided metadata",
            }
        )
