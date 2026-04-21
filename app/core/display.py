from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from decimal import Decimal

MISSING_LABEL = "—"


class BikeLike(Protocol):
    bike_number: str
    model: str


class DisplayNameLike(Protocol):
    @property
    def display_name(self) -> str: ...


def bike_label(bike: BikeLike | None) -> str:
    if bike is None:
        return MISSING_LABEL
    return f"{bike.bike_number} — {bike.model}"


def display_name_label(item: DisplayNameLike | None) -> str:
    if item is None:
        return MISSING_LABEL
    return item.display_name


def optional_text_label(text: str | None) -> str:
    return text or MISSING_LABEL


def optional_minutes_label(minutes: int | None) -> str:
    return f"{minutes} мин." if minutes else MISSING_LABEL


def optional_money_label(amount: Decimal | None) -> str:
    return f"{amount} ₽" if amount else MISSING_LABEL
