"""Inline keyboard builders for bike usage and shift flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    UsageActiveStoreCB,
    UsageBikeSelectCB,
    UsageConfirmCB,
    UsageCourierSelectCB,
    UsageMenuCB,
    UsageReturnBikeCB,
    UsageReturnConfirmCB,
)

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.admin_user import AdminUser
    from app.db.models.bike import Bike
    from app.db.models.bike_usage_log import BikeUsageLog
    from app.db.models.store import Store


def usage_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: take bike / return bike / active shifts."""
    b = InlineKeyboardBuilder()
    b.button(text="🚴 Взял байк", callback_data=UsageMenuCB(action="take"))
    b.button(text="🔙 Вернул байк", callback_data=UsageMenuCB(action="return"))
    b.button(text="👀 Кто на байке", callback_data=UsageMenuCB(action="active"))
    b.button(text="← Назад", callback_data=UsageMenuCB(action="back"))
    b.adjust(2, 1, 1)
    return b.as_markup()


def usage_active_store_select_kb(stores: list[Store]) -> InlineKeyboardMarkup:
    """Store filter for active shifts."""
    b = InlineKeyboardBuilder()
    b.button(
        text="📦 Все склады",
        callback_data=UsageActiveStoreCB(store_id=0),
    )
    for store in stores:
        b.button(
            text=f"🏪 {store.display_name}",
            callback_data=UsageActiveStoreCB(store_id=store.id),
        )
    b.button(text="← Назад", callback_data=UsageMenuCB(action="open"))
    b.adjust(2)
    return b.as_markup()


def usage_bike_select_kb(bikes: list[Bike], store_id: int) -> InlineKeyboardMarkup:
    """List of available bikes for taking."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        b.button(
            text=f"🚲 {bike.bike_number} — {bike.model}",
            callback_data=UsageBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_courier_select_kb(
    couriers: list[AdminUser],
    bike_id: int,
    store_id: int,
) -> InlineKeyboardMarkup:
    """List of couriers to assign to the shift."""
    b = InlineKeyboardBuilder()
    for courier in couriers:
        b.button(
            text=f"👤 {courier.display_name}",
            callback_data=UsageCourierSelectCB(
                courier_id=courier.id,
                bike_id=bike_id,
                store_id=store_id,
            ),
        )
    b.button(text="← Отмена", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(couriers) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_confirm_take_kb() -> InlineKeyboardMarkup:
    """Confirm / cancel taking a bike."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=UsageConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=UsageConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def usage_active_logs_kb(logs: list[BikeUsageLog]) -> InlineKeyboardMarkup:
    """List of active shifts with return buttons."""
    b = InlineKeyboardBuilder()
    for log in logs:
        courier_name = log.courier.display_name if log.courier else "—"
        bike_num = log.bike.bike_number if log.bike else "—"
        started = log.started_at.strftime("%H:%M")
        b.button(
            text=f"🔙 {bike_num} • {courier_name} ({started})",
            callback_data=UsageReturnBikeCB(log_id=log.id),
        )
    b.button(text="← Назад", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(logs) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_return_confirm_kb(log_id: int) -> InlineKeyboardMarkup:
    """Confirm returning a bike."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, вернул",
        callback_data=UsageReturnConfirmCB(log_id=log_id, confirm=True),
    )
    b.button(
        text="❌ Отмена",
        callback_data=UsageReturnConfirmCB(log_id=log_id, confirm=False),
    )
    b.adjust(2)
    return b.as_markup()
