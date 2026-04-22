"""Inline keyboard builders for bike catalog flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    AddBikeConfirmCB,
    BikeCardCB,
    BikeDecommissionCB,
    BikeListCB,
    BikeMenuCB,
    BikeStatusCB,
    BreakdownHistoryCB,
    StatusFilterCB,
)
from app.core.display import bike_status_badge, bike_status_emoji
from app.db.models.bike import BikeStatus

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.bike import Bike

ITEMS_PER_PAGE = 5


def bike_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: list bikes / add bike."""
    b = InlineKeyboardBuilder()
    b.button(text="📋 Список байков", callback_data=BikeMenuCB(action="list"))
    b.button(text="➕ Добавить байк", callback_data=BikeMenuCB(action="add"))
    b.button(text="← Назад", callback_data=BikeMenuCB(action="back"))
    b.adjust(2, 1)
    return b.as_markup()


def status_filter_kb(store_id: int) -> InlineKeyboardMarkup:
    """Filter by status before showing the list."""
    b = InlineKeyboardBuilder()
    b.button(text="📊 Все", callback_data=StatusFilterCB(store_id=store_id, status="all"))
    for status in BikeStatus:
        b.button(
            text=bike_status_badge(status),
            callback_data=StatusFilterCB(store_id=store_id, status=status.value),
        )
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(3, 2, 1)
    return b.as_markup()


def bike_list_kb(
    bikes: list[Bike],
    page: int,
    total: int,
    store_id: int,
    status: str,
) -> InlineKeyboardMarkup:
    """Paginated list of bikes."""
    b = InlineKeyboardBuilder()

    for bike in bikes:
        b.button(
            text=f"{bike_status_emoji(bike.status)} {bike.bike_number} — {bike.model}",
            callback_data=BikeCardCB(bike_id=bike.id),
        )

    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    nav_buttons: list[tuple[str, BikeListCB]] = []

    if page > 0:
        nav_buttons.append(
            (
                "◀️",
                BikeListCB(store_id=store_id, status=status, page=page - 1),
            ),
        )

    nav_buttons.append(
        (
            f"📄 {page + 1}/{total_pages}",
            BikeListCB(store_id=store_id, status=status, page=page),
        ),
    )

    if (page + 1) < total_pages:
        nav_buttons.append(
            (
                "▶️",
                BikeListCB(store_id=store_id, status=status, page=page + 1),
            ),
        )

    for text, cb in nav_buttons:
        b.button(text=text, callback_data=cb)

    b.button(text="← Назад", callback_data=BikeMenuCB(action="open"))

    bike_rows = [1] * len(bikes)
    b.adjust(*bike_rows, len(nav_buttons), 1)

    return b.as_markup()


def bike_card_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Action buttons on a bike card."""
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Изменить статус", callback_data=BikeStatusCB(bike_id=bike_id, status="pick"))
    b.button(
        text="⚫ Списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=False),
    )
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(2, 1)
    return b.as_markup()


def bike_status_select_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Choose new status for a bike."""
    b = InlineKeyboardBuilder()
    for status in BikeStatus:
        b.button(
            text=bike_status_badge(status),
            callback_data=BikeStatusCB(bike_id=bike_id, status=status.value),
        )
    b.button(text="← Отмена", callback_data=BikeCardCB(bike_id=bike_id))
    b.adjust(2, 2, 1)
    return b.as_markup()


def confirm_decommission_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Yes / No confirmation for decommissioning."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=True),
    )
    b.button(text="❌ Отмена", callback_data=BikeCardCB(bike_id=bike_id))
    b.adjust(2)
    return b.as_markup()


def add_bike_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm / cancel adding a new bike."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сохранить", callback_data=AddBikeConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=AddBikeConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def bike_card_actions_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Action buttons on a bike card with breakdown history link."""
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Изменить статус", callback_data=BikeStatusCB(bike_id=bike_id, status="pick"))
    b.button(
        text="⚫ Списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=False),
    )
    b.button(text="📋 Поломки", callback_data=BreakdownHistoryCB(bike_id=bike_id))
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(2, 1, 1)
    return b.as_markup()
