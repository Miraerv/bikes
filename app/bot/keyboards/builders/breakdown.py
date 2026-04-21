"""Inline keyboard builders for breakdown flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    BikeCardCB,
    BreakdownBikeSelectCB,
    BreakdownConfirmCB,
    BreakdownCourierSelectCB,
    BreakdownDetailCB,
    BreakdownHistoryCB,
    BreakdownMenuCB,
    BreakdownSkipPhotoCB,
    BreakdownTypeCB,
)
from app.core.display import bike_status_emoji, breakdown_type_badge
from app.db.models.bike_breakdown import BreakdownType

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.admin_user import AdminUser
    from app.db.models.bike import Bike
    from app.db.models.bike_breakdown import BikeBreakdown


def breakdown_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: create breakdown / back."""
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Создать поломку", callback_data=BreakdownMenuCB(action="create"))
    b.button(text="← Назад", callback_data=BreakdownMenuCB(action="back"))
    b.adjust(1)
    return b.as_markup()


def breakdown_bike_select_kb(
    bikes: list[Bike],
    store_id: int,
) -> InlineKeyboardMarkup:
    """List of bikes at the store, excluding decommissioned bikes."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        b.button(
            text=f"{bike_status_emoji(bike.status)} {bike.bike_number} — {bike.model}",
            callback_data=BreakdownBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_type_kb() -> InlineKeyboardMarkup:
    """Choose breakdown type."""
    b = InlineKeyboardBuilder()
    for bd_type in BreakdownType:
        b.button(
            text=breakdown_type_badge(bd_type),
            callback_data=BreakdownTypeCB(bd_type=bd_type.value),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def breakdown_photo_kb() -> InlineKeyboardMarkup:
    """Photo upload: skip or finish."""
    b = InlineKeyboardBuilder()
    b.button(text="⏭ Пропустить", callback_data=BreakdownSkipPhotoCB(action="skip"))
    b.button(text="✅ Готово", callback_data=BreakdownSkipPhotoCB(action="done"))
    b.adjust(2)
    return b.as_markup()


def breakdown_courier_select_kb(
    couriers: list[AdminUser],
) -> InlineKeyboardMarkup:
    """List of couriers for manual selection during breakdown creation."""
    b = InlineKeyboardBuilder()
    for courier in couriers:
        b.button(
            text=f"👤 {courier.display_name}",
            callback_data=BreakdownCourierSelectCB(courier_id=courier.id),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    rows = [1] * len(couriers) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel breakdown creation."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сохранить", callback_data=BreakdownConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=BreakdownConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def breakdown_history_kb(
    breakdowns: list[BikeBreakdown],
    bike_id: int,
) -> InlineKeyboardMarkup:
    """List breakdowns for a bike card; each item opens details."""
    b = InlineKeyboardBuilder()
    for bd in breakdowns:
        reported = bd.reported_at.strftime("%d.%m") if bd.reported_at else "—"
        photo_icon = "📷" if bd.photos else ""
        b.button(
            text=f"{breakdown_type_badge(bd.breakdown_type)} ({reported}) {photo_icon}",
            callback_data=BreakdownDetailCB(breakdown_id=bd.id, bike_id=bike_id),
        )
    b.button(text="← Назад", callback_data=BikeCardCB(bike_id=bike_id))
    rows = [1] * len(breakdowns) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_detail_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Back button from breakdown detail to breakdown list."""
    b = InlineKeyboardBuilder()
    b.button(text="← К списку поломок", callback_data=BreakdownHistoryCB(bike_id=bike_id))
    b.adjust(1)
    return b.as_markup()
