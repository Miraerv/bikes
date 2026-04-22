"""BIKE-21 — List bikes handler (filtered, paginated)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import func, select

from app.bot.keyboards.builders import (
    ITEMS_PER_PAGE,
    bike_list_kb,
    bike_menu_kb,
    status_filter_kb,
    store_select_kb,
)
from app.bot.keyboards.callbacks import BikeListCB, BikeMenuCB, StatusFilterCB, StoreSelectCB
from app.core.store_access import apply_store_scope, get_accessible_stores, guard_store_access
from app.db.models.bike import Bike, BikeStatus

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.bot_user import BotUser

router = Router(name="list_bikes")


# ── Step 1: Choose store ────────────────────────────────────────────────


@router.callback_query(BikeMenuCB.filter(F.action == "list"))
async def choose_store(
    callback: CallbackQuery,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Show store selector for filtering bikes."""
    await callback.answer()

    stores = await get_accessible_stores(market_session, bot_user)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Список байков</b>\n\nВыберите склад:",
        reply_markup=store_select_kb(stores, purpose="filter"),
    )


# ── Step 2: Choose status filter ────────────────────────────────────────


@router.callback_query(StoreSelectCB.filter(F.purpose == "filter"))
async def choose_status(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    bot_user: BotUser | None = None,
) -> None:
    """Show status filter after store is selected."""
    if callback_data.store_id > 0 and not await guard_store_access(
        callback,
        bot_user,
        callback_data.store_id,
    ):
        return
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📊 <b>Фильтр по статусу</b>\n\nВыберите статус:",
        reply_markup=status_filter_kb(callback_data.store_id),
    )


# ── Step 3: Show filtered list ──────────────────────────────────────────


@router.callback_query(StatusFilterCB.filter())
async def show_filtered_list(
    callback: CallbackQuery,
    callback_data: StatusFilterCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Load bikes with filters and show paginated list (page 0)."""
    if callback_data.store_id > 0 and not await guard_store_access(
        callback,
        bot_user,
        callback_data.store_id,
    ):
        return
    await callback.answer()
    await _show_bike_list(
        callback,
        callback_data.store_id,
        callback_data.status,
        0,
        market_session,
        bot_user,
    )


@router.callback_query(BikeListCB.filter())
async def paginate_list(
    callback: CallbackQuery,
    callback_data: BikeListCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Handle page navigation."""
    if callback_data.store_id > 0 and not await guard_store_access(
        callback,
        bot_user,
        callback_data.store_id,
    ):
        return
    await callback.answer()
    await _show_bike_list(
        callback,
        callback_data.store_id,
        callback_data.status,
        callback_data.page,
        market_session,
        bot_user,
    )


# ── Shared list rendering ──────────────────────────────────────────────


async def _show_bike_list(
    callback: CallbackQuery,
    store_id: int,
    status: str,
    page: int,
    session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Query bikes and render paginated inline keyboard."""
    # Build base query
    query = apply_store_scope(select(Bike), Bike.store_id, bot_user)
    count_query = apply_store_scope(select(func.count(Bike.id)), Bike.store_id, bot_user)

    if store_id > 0:
        query = query.where(Bike.store_id == store_id)
        count_query = count_query.where(Bike.store_id == store_id)

    if status != "all":
        bike_status = BikeStatus(status)
        query = query.where(Bike.status == bike_status)
        count_query = count_query.where(Bike.status == bike_status)

    # Total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    if total == 0:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Байков не найдено.",
            reply_markup=bike_menu_kb(),
        )
        return

    # Fetch page
    query = query.order_by(Bike.bike_number).offset(page * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE)
    result = await session.execute(query)
    bikes = list(result.scalars().all())

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🚲 <b>Байки</b> — найдено: {total}",
        reply_markup=bike_list_kb(bikes, page, total, store_id, status),
    )
