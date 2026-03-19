"""BIKE-60-62 — Dashboard 'Парк байков': fleet overview + per-store breakdown."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import func, select

from app.bot.keyboards.builders import (
    STATUS_EMOJI,
    STATUS_LABEL,
    dashboard_back_kb,
    dashboard_stores_kb,
    main_menu_kb,
)
from app.bot.keyboards.callbacks import DashboardMenuCB, DashboardStoreCB
from app.core.config import settings
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_repair import BikeRepair
from app.db.models.bike_usage_log import BikeUsageLog
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="dashboard")


# ── Helper: aggregate bike counts ───────────────────────────────────────


async def _get_status_counts(
    session: AsyncSession,
    store_id: int | None = None,
) -> dict[str, int]:
    """Return {status_value: count} dict.  If store_id is given, filter by it."""
    query = select(Bike.status, func.count(Bike.id)).group_by(Bike.status)
    if store_id is not None:
        query = query.where(Bike.store_id == store_id)
    result = await session.execute(query)
    return {status.value: cnt for status, cnt in result.all()}


async def _get_stores_with_counts(
    session: AsyncSession,
) -> list[tuple[Store, dict[str, int]]]:
    """Return list of (Store, counts_dict) sorted by display_name."""
    # Fetch express stores
    stores_result = await session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(stores_result.scalars().all())

    # Aggregate counts per store
    query = (
        select(Bike.store_id, Bike.status, func.count(Bike.id))
        .group_by(Bike.store_id, Bike.status)
    )
    result = await session.execute(query)

    store_counts: dict[int, dict[str, int]] = defaultdict(dict)
    for sid, status, cnt in result.all():
        store_counts[sid][status.value] = cnt

    return [(store, store_counts.get(store.id, {})) for store in stores]


# ── Dashboard: overall fleet stats ─────────────────────────────────────


def _format_overall(counts: dict[str, int]) -> str:
    """Format the overall fleet stats text."""
    total = sum(counts.values())
    lines = [
        "📈 <b>Парк байков</b>\n",
        f"Всего: <b>{total}</b>",
    ]
    for status in BikeStatus:
        emoji = STATUS_EMOJI[status.value]
        label = STATUS_LABEL[status.value]
        cnt = counts.get(status.value, 0)
        lines.append(f"{emoji} {label}: <b>{cnt}</b>")
    lines.append("\n<i>Выберите склад для детализации:</i>")
    return "\n".join(lines)


@router.callback_query(DashboardMenuCB.filter(F.action == "open"))
async def open_dashboard(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Show overall fleet statistics with per-store buttons."""
    await callback.answer()

    counts = await _get_status_counts(market_session)
    stores_data = await _get_stores_with_counts(market_session)

    await callback.message.edit_text(  # type: ignore[union-attr]
        _format_overall(counts),
        reply_markup=dashboard_stores_kb(stores_data),
    )


@router.callback_query(DashboardMenuCB.filter(F.action == "back"))
async def dashboard_back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu from dashboard."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


# ── Store detail ───────────────────────────────────────────────────────


@router.callback_query(DashboardStoreCB.filter())
async def store_detail(
    callback: CallbackQuery,
    callback_data: DashboardStoreCB,
    market_session: AsyncSession,
) -> None:
    """Show per-store bike stats + active shifts & repairs."""
    await callback.answer()

    store_id = callback_data.store_id

    # Fetch store
    store_result = await market_session.execute(
        select(Store).where(Store.id == store_id),
    )
    store = store_result.scalar_one_or_none()
    store_name = store.display_name if store else f"#{store_id}"

    # Bike counts by status
    counts = await _get_status_counts(market_session, store_id=store_id)
    total = sum(counts.values())

    # Active shifts (ended_at IS NULL)
    active_shifts_result = await market_session.execute(
        select(func.count(BikeUsageLog.id)).where(
            BikeUsageLog.store_id == store_id,
            BikeUsageLog.ended_at.is_(None),
        ),
    )
    active_shifts = active_shifts_result.scalar() or 0

    # Active repairs (completed_at IS NULL)
    active_repairs_result = await market_session.execute(
        select(func.count(BikeRepair.id)).where(
            BikeRepair.store_id == store_id,
            BikeRepair.completed_at.is_(None),
        ),
    )
    active_repairs = active_repairs_result.scalar() or 0

    # Format text
    lines = [
        f"🏪 <b>Склад: {store_name}</b>\n",
        f"Байки: <b>{total}</b>",
    ]
    for status in BikeStatus:
        emoji = STATUS_EMOJI[status.value]
        label = STATUS_LABEL[status.value]
        cnt = counts.get(status.value, 0)
        lines.append(f"{emoji} {label}: <b>{cnt}</b>")

    lines.append("")
    lines.append(f"👤 Активных смен: <b>{active_shifts}</b>")
    lines.append(f"🔧 В ремонте сейчас: <b>{active_repairs}</b>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=dashboard_back_kb(),
    )
