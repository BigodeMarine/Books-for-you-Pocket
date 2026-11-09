"""Controlled values used by the catalog and offer models."""

from enum import Enum

from sqlalchemy import Enum as SQLAlchemyEnum


class WorkType(str, Enum):
    """Kinds of intellectual works represented in the catalog."""

    BOOK = "book"
    MANGA = "manga"
    COMIC = "comic"


class EditionFormat(str, Enum):
    """Formats available for a specific edition."""

    PAPERBACK = "paperback"
    HARDCOVER = "hardcover"
    EBOOK = "ebook"
    AUDIOBOOK = "audiobook"
    DIGITAL = "digital"
    OTHER = "other"


class MetadataSource(str, Enum):
    """Sources from which edition metadata may originate."""

    GOOGLE_BOOKS = "google_books"
    OPEN_LIBRARY = "open_library"
    MANUAL = "manual"


class OfferCondition(str, Enum):
    """Condition of the item included in an offer."""

    NEW = "new"
    USED = "used"


class AvailabilityStatus(str, Enum):
    """Availability states tracked for offers and their price history."""

    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    UNKNOWN = "unknown"


def database_enum(enum_class: type[Enum], name: str) -> SQLAlchemyEnum:
    """Create a portable validated SQL enum constraint that stores enum values."""
    return SQLAlchemyEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
