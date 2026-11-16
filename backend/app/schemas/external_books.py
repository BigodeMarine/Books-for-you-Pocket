"""Schemas for external book searches and normalized Google Books results."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExternalBookSearchQuery(BaseModel):
    """Validated search criteria and pagination for an external book search."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    author: str | None = None
    isbn: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=40)

    @field_validator("title", "author", "isbn")
    @classmethod
    def strip_nonempty_criteria(cls, value: str | None) -> str | None:
        """Normalize search text and reject whitespace-only criteria."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Search criteria cannot be empty")
        return normalized

    @model_validator(mode="after")
    def require_exactly_one_criterion(self) -> Self:
        """Require one non-empty title, author, or ISBN criterion."""
        criteria = [self.title, self.author, self.isbn]
        if sum(value is not None for value in criteria) != 1:
            raise ValueError("Provide exactly one of title, author, or isbn")
        return self


class ExternalBookRead(BaseModel):
    """Application-owned representation of a book volume from a provider."""

    provider_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    published_date: str | None = None
    description: str | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    page_count: int | None = None
    categories: list[str] = Field(default_factory=list)
    language: str | None = None
    thumbnail_url: str | None = None
    info_link: str | None = None
    preview_link: str | None = None
