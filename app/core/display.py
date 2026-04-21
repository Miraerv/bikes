from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

MISSING_LABEL = "—"
UNKNOWN_EMOJI = "❓"

STATUS_EMOJI: dict[str, str] = {
    "online": "🟢",
    "inspection": "🟡",
    "repair": "🔴",
    "decommissioned": "⚫",
}

STATUS_LABEL: dict[str, str] = {
    "online": "На линии",
    "inspection": "Проверка",
    "repair": "Ремонт",
    "decommissioned": "Списан",
}

BREAKDOWN_TYPE_EMOJI: dict[str, str] = {
    "brakes": "🛑",
    "wheel": "🛞",
    "battery": "🔋",
    "motor": "⚙️",
    "frame": "🪨",
    "electronics": "💡",
    "other": UNKNOWN_EMOJI,
}

BREAKDOWN_TYPE_LABEL: dict[str, str] = {
    "brakes": "Тормоза",
    "wheel": "Колесо",
    "battery": "Аккумулятор",
    "motor": "Двигатель",
    "frame": "Рама",
    "electronics": "Электроника",
    "other": "Другое",
}


class BikeLike(Protocol):
    bike_number: str
    model: str


class DisplayNameLike(Protocol):
    @property
    def display_name(self) -> str: ...


class DisplayValueLike(Protocol):
    @property
    def value(self) -> str: ...


def _display_key(value: str | DisplayValueLike) -> str:
    if isinstance(value, str):
        return value
    return value.value


def _display_label(value: str | DisplayValueLike, labels: Mapping[str, str]) -> str:
    key = _display_key(value)
    return labels.get(key, key)


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


def bike_status_emoji(status: str | DisplayValueLike) -> str:
    return STATUS_EMOJI.get(_display_key(status), UNKNOWN_EMOJI)


def bike_status_label(status: str | DisplayValueLike) -> str:
    return _display_label(status, STATUS_LABEL)


def bike_status_badge(status: str | DisplayValueLike) -> str:
    return f"{bike_status_emoji(status)} {bike_status_label(status)}"


def breakdown_type_emoji(breakdown_type: str | DisplayValueLike) -> str:
    return BREAKDOWN_TYPE_EMOJI.get(_display_key(breakdown_type), UNKNOWN_EMOJI)


def breakdown_type_label(breakdown_type: str | DisplayValueLike) -> str:
    return _display_label(breakdown_type, BREAKDOWN_TYPE_LABEL)


def breakdown_type_badge(breakdown_type: str | DisplayValueLike) -> str:
    return f"{breakdown_type_emoji(breakdown_type)} {breakdown_type_label(breakdown_type)}"
