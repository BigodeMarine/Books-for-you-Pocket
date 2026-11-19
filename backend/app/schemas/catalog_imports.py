"""Schemas for importing Google Books volumes into the catalog."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EditionFormat, WorkType


class ExistingWorkTarget(BaseModel):
    """Select an existing catalog work as the import destination."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["existing"]
    work_id: UUID


class NewWorkTarget(BaseModel):
    """Request creation of a work with the supplied domain type."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["new"]
    work_type: WorkType


WorkTarget = Annotated[
    ExistingWorkTarget | NewWorkTarget,
    Field(discriminator="kind"),
]


class GoogleBooksImportRequest(BaseModel):
    """Input identifying a Google Books volume and its catalog destination."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    work_target: WorkTarget
    edition_format: EditionFormat | None = None
    language_fallback: str | None = None


WarningCode = Literal[
    "isbn_invalid",
    "isbn_already_assigned",
    "publication_date_incomplete",
    "publication_date_invalid",
    "author_ambiguous",
    "genre_ambiguous",
    "genre_slug_collision",
]


class GoogleBooksImportWarning(BaseModel):
    """A stable, user-readable warning produced during an import."""

    model_config = ConfigDict(extra="forbid")

    code: WarningCode
    message: str


class GoogleBooksImportResponse(BaseModel):
    """Identifiers and outcome of a Google Books catalog import."""

    model_config = ConfigDict(extra="forbid")

    work_id: UUID
    edition_id: UUID
    work_created: bool
    edition_created: bool
    warnings: list[GoogleBooksImportWarning] = Field(default_factory=list)
