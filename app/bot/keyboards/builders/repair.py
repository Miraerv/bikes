"""Inline keyboard builders for repair flows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    RepairBikeSelectCB,
    RepairBreakdownSelectCB,
    RepairBreakdownSkipCB,
    RepairCompleteConfirmCB,
    RepairMechanicSelectCB,
    RepairMenuCB,
    RepairPickupConfirmCB,
    RepairSelectCB,
)
from app.core.display import bike_status_emoji, breakdown_type_badge

if TYPE_CHECKING:
    from collections.abc import Sequence

    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.bike import Bike
    from app.db.models.bike_breakdown import BikeBreakdown
    from app.db.models.bike_repair import BikeRepair


class MechanicOption(Protocol):
    """Minimal shape needed to render a mechanic selection button."""

    id: int
    name: str


def repair_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: pickup bike / complete / my repairs / back."""
    b = InlineKeyboardBuilder()
    b.button(text="📥 Забрал байк", callback_data=RepairMenuCB(action="pickup"))
    b.button(text="✅ Байк готов", callback_data=RepairMenuCB(action="complete"))
    b.button(text="📋 Мои ремонты", callback_data=RepairMenuCB(action="my_repairs"))
    b.button(text="← Назад", callback_data=RepairMenuCB(action="back"))
    b.adjust(2, 1, 1)
    return b.as_markup()


def repair_bike_select_kb(
    bikes: list[Bike],
    store_id: int,
) -> InlineKeyboardMarkup:
    """List of bikes available for repair pickup."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        b.button(
            text=f"{bike_status_emoji(bike.status)} {bike.bike_number} — {bike.model}",
            callback_data=RepairBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_breakdown_select_kb(
    breakdowns: list[BikeBreakdown],
) -> InlineKeyboardMarkup:
    """List of open breakdowns for linking to a repair + skip button."""
    b = InlineKeyboardBuilder()
    for bd in breakdowns:
        reported = bd.reported_at.strftime("%d.%m")
        b.button(
            text=f"{breakdown_type_badge(bd.breakdown_type)} ({reported})",
            callback_data=RepairBreakdownSelectCB(breakdown_id=bd.id),
        )
    b.button(text="⏭ Без привязки", callback_data=RepairBreakdownSkipCB(action="skip"))
    rows = [1] * len(breakdowns) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_mechanic_select_kb(
    mechanics: Sequence[MechanicOption],
) -> InlineKeyboardMarkup:
    """List of mechanics for selection."""
    b = InlineKeyboardBuilder()
    for mech in mechanics:
        b.button(
            text=f"🔧 {mech.name}",
            callback_data=RepairMechanicSelectCB(mechanic_id=mech.id),
        )
    b.button(text="← Отмена", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(mechanics) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_pickup_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel repair pickup."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=RepairPickupConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=RepairPickupConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def repair_active_list_kb(repairs: list[BikeRepair]) -> InlineKeyboardMarkup:
    """List of active repairs for completion."""
    b = InlineKeyboardBuilder()
    for repair in repairs:
        bike_num = repair.bike.bike_number if repair.bike else "—"
        picked = repair.picked_up_at.strftime("%d.%m %H:%M")
        b.button(
            text=f"🔴 {bike_num} (с {picked})",
            callback_data=RepairSelectCB(repair_id=repair.id),
        )
    b.button(text="← Назад", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(repairs) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_complete_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel repair completion."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Завершить", callback_data=RepairCompleteConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=RepairCompleteConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def repair_my_list_kb(
    repairs: list[BikeRepair],  # noqa: ARG001
) -> InlineKeyboardMarkup:
    """List of all repairs for a mechanic."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад", callback_data=RepairMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()
