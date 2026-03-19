"""BIKE-70-75 — Analytics reports: breakdowns, bikes, repairs, couriers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.bot.keyboards.builders import (
    BREAKDOWN_TYPE_EMOJI,
    BREAKDOWN_TYPE_LABEL,
    analytics_back_kb,
    analytics_menu_kb,
    main_menu_kb,
)
from app.bot.keyboards.callbacks import AnalyticsMenuCB
from app.db.models.admin_user import AdminUser
from app.db.models.bike import Bike
from app.db.models.bike_breakdown import BikeBreakdown
from app.db.models.bike_repair import BikeRepair
from app.db.models.bike_usage_log import BikeUsageLog
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="analytics")

# ── Period helper ───────────────────────────────────────────────────────

REPORT_DAYS = 30


def _period_start() -> datetime:
    return datetime.now() - timedelta(days=REPORT_DAYS)


# ── Menu ────────────────────────────────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "open"))
async def open_analytics_menu(callback: CallbackQuery) -> None:
    """Show analytics sub-menu with report buttons."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📊 <b>Аналитика</b>\n\n"
        f"Отчёты за последние {REPORT_DAYS} дней.\n"
        "Выберите отчёт:",
        reply_markup=analytics_menu_kb(),
    )


@router.callback_query(AnalyticsMenuCB.filter(F.action == "back"))
async def analytics_back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu from analytics."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


# ── BIKE-70: Breakdowns per month ──────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "breakdowns_month"))
async def report_breakdowns_month(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: breakdowns in the last month — total, by store, by type."""
    await callback.answer()
    since = _period_start()

    # Total count
    total_q = select(func.count(BikeBreakdown.id)).where(
        BikeBreakdown.reported_at >= since,
    )
    total = (await market_session.execute(total_q)).scalar() or 0

    # By store
    store_q = (
        select(Store.street, Store.title, func.count(BikeBreakdown.id))
        .join(BikeBreakdown, BikeBreakdown.store_id == Store.id)
        .where(BikeBreakdown.reported_at >= since)
        .group_by(Store.id)
        .order_by(func.count(BikeBreakdown.id).desc())
    )
    store_rows = (await market_session.execute(store_q)).all()

    # By type
    type_q = (
        select(BikeBreakdown.breakdown_type, func.count(BikeBreakdown.id))
        .where(BikeBreakdown.reported_at >= since)
        .group_by(BikeBreakdown.breakdown_type)
        .order_by(func.count(BikeBreakdown.id).desc())
    )
    type_rows = (await market_session.execute(type_q)).all()

    # Format
    lines = [
        f"📋 <b>Поломки за {REPORT_DAYS} дней</b>\n",
        f"Всего: <b>{total}</b>\n",
    ]

    if store_rows:
        lines.append("<b>По складам:</b>")
        for street, title, cnt in store_rows:
            name = street or title or "—"
            lines.append(f"  🏪 {name}: <b>{cnt}</b>")
        lines.append("")

    if type_rows:
        lines.append("<b>По типам:</b>")
        for bd_type, cnt in type_rows:
            emoji = BREAKDOWN_TYPE_EMOJI.get(bd_type.value, "❓")
            label = BREAKDOWN_TYPE_LABEL.get(bd_type.value, bd_type.value)
            lines.append(f"  {emoji} {label}: <b>{cnt}</b>")

    if total == 0:
        lines.append("\n<i>Поломок не зафиксировано 🎉</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )


# ── BIKE-71: Breakdowns by couriers ────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "breakdowns_couriers"))
async def report_breakdowns_couriers(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: breakdown count per courier (who breaks bikes the most)."""
    await callback.answer()
    since = _period_start()

    q = (
        select(
            AdminUser.name,
            AdminUser.surname,
            func.count(BikeBreakdown.id).label("cnt"),
        )
        .join(AdminUser, AdminUser.id == BikeBreakdown.courier_id)
        .where(BikeBreakdown.reported_at >= since)
        .group_by(AdminUser.id)
        .order_by(func.count(BikeBreakdown.id).desc())
        .limit(10)
    )
    rows = (await market_session.execute(q)).all()

    lines = ["👤 <b>Поломки по курьерам (топ-10)</b>\n"]

    if rows:
        for i, (name, surname, cnt) in enumerate(rows, 1):
            full = f"{name} {surname}" if surname else name
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"  {medal} {full}: <b>{cnt}</b>")
    else:
        lines.append("<i>Нет данных за период</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )


# ── BIKE-72: Unreliable bikes ──────────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "unreliable_bikes"))
async def report_unreliable_bikes(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: top-10 bikes by breakdown count."""
    await callback.answer()
    since = _period_start()

    q = (
        select(
            Bike.bike_number,
            Bike.model,
            func.count(BikeBreakdown.id).label("cnt"),
        )
        .join(BikeBreakdown, BikeBreakdown.bike_id == Bike.id)
        .where(BikeBreakdown.reported_at >= since)
        .group_by(Bike.id)
        .order_by(func.count(BikeBreakdown.id).desc())
        .limit(10)
    )
    rows = (await market_session.execute(q)).all()

    lines = ["🔴 <b>Ненадёжные байки (топ-10)</b>\n"]

    if rows:
        for i, (number, model, cnt) in enumerate(rows, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"  {medal} {number} ({model}): <b>{cnt} поломок</b>")
    else:
        lines.append("<i>Нет поломок за период 🎉</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )


# ── BIKE-73: Bike repairs ─────────────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "bike_repairs"))
async def report_bike_repairs(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: top-10 bikes by repair count, with total duration & cost."""
    await callback.answer()
    since = _period_start()

    q = (
        select(
            Bike.bike_number,
            Bike.model,
            func.count(BikeRepair.id).label("cnt"),
            func.coalesce(func.sum(BikeRepair.repair_duration_minutes), 0).label("total_minutes"),
            func.coalesce(func.sum(BikeRepair.cost), 0).label("total_cost"),
        )
        .join(BikeRepair, BikeRepair.bike_id == Bike.id)
        .where(BikeRepair.picked_up_at >= since)
        .group_by(Bike.id)
        .order_by(func.count(BikeRepair.id).desc())
        .limit(10)
    )
    rows = (await market_session.execute(q)).all()

    lines = ["🛠 <b>Ремонты (топ-10 байков)</b>\n"]

    if rows:
        for i, (number, model, cnt, minutes, cost) in enumerate(rows, 1):
            hours = int(minutes) // 60
            mins = int(minutes) % 60
            duration = f"{hours}ч {mins}м" if hours else f"{mins}м"
            cost_str = f"{cost:,.0f}₽" if cost else "—"
            lines.append(
                f"  {i}. <b>{number}</b> ({model})\n"
                f"      ремонтов: {cnt} • время: {duration} • стоимость: {cost_str}",
            )
    else:
        lines.append("<i>Нет ремонтов за период</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )


# ── BIKE-74: Downtime ─────────────────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "downtime"))
async def report_downtime(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: downtime % — repair hours / total hours since commissioned."""
    await callback.answer()
    now = datetime.now()

    # Fetch bikes with their repairs
    q = (
        select(Bike)
        .options(joinedload(Bike.repairs))
        .where(Bike.status != "decommissioned")
    )
    result = await market_session.execute(q)
    bikes = result.unique().scalars().all()

    # Calculate downtime for each bike
    bike_stats: list[tuple[str, str, float, int]] = []
    for bike in bikes:
        total_hours = max(
            1,
            (
                now
                - datetime.combine(bike.commissioned_at, datetime.min.time())
            ).total_seconds()
            / 3600,
        )
        repair_hours = 0.0
        for repair in bike.repairs:
            end = repair.completed_at or now
            repair_hours += (end - repair.picked_up_at).total_seconds() / 3600

        pct = (repair_hours / total_hours) * 100
        bike_stats.append((bike.bike_number, bike.model, pct, int(repair_hours)))

    # Sort by downtime % descending
    bike_stats.sort(key=lambda x: x[2], reverse=True)
    top = bike_stats[:10]

    lines = ["⏱ <b>Даунтайм (топ-10)</b>\n"]

    if top:
        for i, (number, model, pct, hours) in enumerate(top, 1):
            bar = _progress_bar(pct)
            lines.append(
                f"  {i}. <b>{number}</b> ({model})\n"
                f"      {bar} {pct:.1f}% ({hours}ч в ремонте)",
            )
    else:
        lines.append("<i>Нет данных</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )


def _progress_bar(pct: float, length: int = 10) -> str:
    """Render a simple text progress bar."""
    filled = min(length, int(pct / 100 * length))
    return "█" * filled + "░" * (length - filled)


# ── BIKE-75: Careful couriers ──────────────────────────────────────────


@router.callback_query(AnalyticsMenuCB.filter(F.action == "careful_couriers"))
async def report_careful_couriers(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Report: couriers ranked by fewest breakdowns (who is the most careful)."""
    await callback.answer()
    since = _period_start()

    # All couriers who had shifts in the period
    breakdown_count = (
        select(
            BikeBreakdown.courier_id,
            func.count(BikeBreakdown.id).label("bd_count"),
        )
        .where(BikeBreakdown.reported_at >= since)
        .group_by(BikeBreakdown.courier_id)
        .subquery()
    )

    q = (
        select(
            AdminUser.name,
            AdminUser.surname,
            func.count(BikeUsageLog.id).label("shift_count"),
            func.coalesce(breakdown_count.c.bd_count, 0).label("bd_count"),
        )
        .join(BikeUsageLog, BikeUsageLog.courier_id == AdminUser.id)
        .outerjoin(breakdown_count, breakdown_count.c.courier_id == AdminUser.id)
        .where(BikeUsageLog.started_at >= since)
        .group_by(AdminUser.id, breakdown_count.c.bd_count)
        .order_by(func.coalesce(breakdown_count.c.bd_count, 0).asc())
        .limit(10)
    )
    rows = (await market_session.execute(q)).all()

    lines = ["✅ <b>Аккуратные курьеры (топ-10)</b>\n"]

    if rows:
        for i, (name, surname, shifts, bds) in enumerate(rows, 1):
            full = f"{name} {surname}" if surname else name
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(
                f"  {medal} {full}\n"
                f"      смен: {shifts} • поломок: {bds}",
            )
    else:
        lines.append("<i>Нет данных за период</i>")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=analytics_back_kb(),
    )
