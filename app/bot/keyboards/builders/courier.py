"""Inline keyboard builders for courier shift flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import CourierMenuCB, CourierTakeConfirmCB

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup


def courier_menu_kb() -> InlineKeyboardMarkup:
    """Courier main menu: take / return bike."""
    b = InlineKeyboardBuilder()
    b.button(text="🚴 Взял байк", callback_data=CourierMenuCB(action="take"))
    b.button(text="🔙 Вернул байк", callback_data=CourierMenuCB(action="return"))
    b.adjust(1)
    return b.as_markup()


def courier_take_confirm_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Confirm / cancel taking a bike."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Подтвердить",
        callback_data=CourierTakeConfirmCB(bike_id=bike_id, action="save"),
    )
    b.button(
        text="❌ Отмена",
        callback_data=CourierTakeConfirmCB(bike_id=bike_id, action="cancel"),
    )
    b.adjust(2)
    return b.as_markup()
