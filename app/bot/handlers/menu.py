"""Bike sub-menu handler — entry point for bike CRUD."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router

from app.bot.keyboards.builders import bike_menu_kb, main_menu_kb
from app.bot.keyboards.callbacks import BikeMenuCB

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery

router = Router(name="menu")


@router.callback_query(BikeMenuCB.filter(F.action == "open"))
async def open_bike_menu(callback: CallbackQuery) -> None:
    """Show bike sub-menu (list / add)."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 <b>Управление байками</b>\n\nВыберите действие:",
        reply_markup=bike_menu_kb(),
    )


@router.callback_query(BikeMenuCB.filter(F.action == "back"))
async def back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )
