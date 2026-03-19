"""BIKE-80..84 — Alert cron tasks and Telegram group notifications.

Three scheduled checks run every N minutes (configurable):
  1. Low bikes on a store  — online bikes < threshold
  2. Long repairs           — repair open > N days
  3. Frequent breakdowns    — bike broken > N times per month

Alerts are deduplicated: if an unread alert of the same type exists for the
same bike/store within the last 24 hours, it is skipped.

Notifications are sent to a Telegram group (``ALERT_CHAT_ID`` in ``.env``).
All group members are expected to be admins.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import func, select

from app.core.config import settings
from app.db.base import market_session_maker
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_alert import AlertType, BikeAlert
from app.db.models.bike_breakdown import BikeBreakdown
from app.db.models.bike_repair import BikeRepair
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram import Bot
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ─────────────────────────────────────────────────────────────


async def _has_recent_alert(
    session: AsyncSession,
    alert_type: AlertType,
    *,
    bike_id: int | None = None,
    store_id: int | None = None,
) -> bool:
    """Return True if an unread alert of the same type exists in the last 24h."""
    threshold = datetime.now() - timedelta(hours=24)
    stmt = (
        select(BikeAlert.id)
        .where(
            BikeAlert.alert_type == alert_type,
            BikeAlert.is_read.is_(False),
            BikeAlert.created_at >= threshold,
        )
        .limit(1)
    )
    if bike_id is not None:
        stmt = stmt.where(BikeAlert.bike_id == bike_id)
    if store_id is not None:
        stmt = stmt.where(BikeAlert.store_id == store_id)
    result = await session.execute(stmt)
    return result.scalar() is not None


async def _send_alert(bot: Bot, message: str) -> None:
    """Send an HTML message to the alert group chat."""
    chat_id = settings.alert_chat_id
    if not chat_id:
        logger.warning("ALERT_CHAT_ID not set — alert logged only: {msg}", msg=message)
        return
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        logger.info("Alert sent to chat {chat_id}", chat_id=chat_id)
    except Exception:
        logger.exception("Failed to send alert to chat {chat_id}", chat_id=chat_id)


# ── BIKE-81: Low bikes on store ────────────────────────────────────────


async def check_low_bikes(bot: Bot) -> None:
    """Alert when online bikes at a store < threshold."""
    threshold = settings.alert_min_bikes
    logger.debug("check_low_bikes: running (threshold={t})", t=threshold)

    async with market_session_maker() as session:
        # Get express stores
        stores_result = await session.execute(
            select(Store).where(
                Store.main_id == "express",
                Store.id.notin_(settings.hidden_store_ids),
            ),
        )
        stores = stores_result.scalars().all()

        for store in stores:
            # Count online bikes
            count_result = await session.execute(
                select(func.count(Bike.id)).where(
                    Bike.store_id == store.id,
                    Bike.status == BikeStatus.ONLINE,
                ),
            )
            online_count = count_result.scalar() or 0

            if online_count >= threshold:
                continue

            # Dedup
            if await _has_recent_alert(session, AlertType.LOW_BIKES, store_id=store.id):
                logger.debug(
                    "check_low_bikes: skipping duplicate for store {s}",
                    s=store.display_name,
                )
                continue

            # Create alert record
            msg = (
                f"⚠️ <b>Мало байков на складе</b>\n\n"
                f"🏪 <b>{store.display_name}</b>\n"
                f"🟢 На линии: <b>{online_count}</b> (порог: {threshold})\n\n"
                f"Необходимо пополнить парк!"
            )
            alert = BikeAlert(
                store_id=store.id,
                alert_type=AlertType.LOW_BIKES,
                message=msg,
            )
            session.add(alert)
            await session.commit()

            await _send_alert(bot, msg)
            logger.info(
                "check_low_bikes: alert created for store {s} (online={c})",
                s=store.display_name,
                c=online_count,
            )


# ── BIKE-82: Long repairs ──────────────────────────────────────────────


async def check_long_repairs(bot: Bot) -> None:
    """Alert when a bike has been in repair > N days."""
    max_days = settings.alert_repair_max_days
    cutoff = datetime.now() - timedelta(days=max_days)
    logger.debug("check_long_repairs: running (max_days={d})", d=max_days)

    async with market_session_maker() as session:
        result = await session.execute(
            select(BikeRepair)
            .where(
                BikeRepair.completed_at.is_(None),
                BikeRepair.picked_up_at < cutoff,
            ),
        )
        stale_repairs = result.scalars().all()

        for repair in stale_repairs:
            bike = repair.bike
            if bike is None:
                continue

            # Dedup
            if await _has_recent_alert(
                session, AlertType.REPAIR_TOO_LONG, bike_id=bike.id,
            ):
                continue

            days_in_repair = (datetime.now() - repair.picked_up_at).days
            mechanic_name = repair.mechanic_name or "—"
            store_name = bike.store.display_name if bike.store else "—"

            msg = (
                f"🔴 <b>Долгий ремонт</b>\n\n"
                f"🚲 <b>{bike.bike_number}</b> — {bike.model}\n"
                f"🏪 {store_name}\n"
                f"🔧 Мастер: {mechanic_name}\n"
                f"📅 В ремонте: <b>{days_in_repair} дн.</b> (порог: {max_days})\n\n"
                f"Требуется внимание!"
            )
            alert = BikeAlert(
                bike_id=bike.id,
                store_id=bike.store_id,
                alert_type=AlertType.REPAIR_TOO_LONG,
                message=msg,
            )
            session.add(alert)
            await session.commit()

            await _send_alert(bot, msg)
            logger.info(
                "check_long_repairs: alert for bike {b} ({d} days)",
                b=bike.bike_number,
                d=days_in_repair,
            )


# ── BIKE-83: Frequent breakdowns ──────────────────────────────────────


async def check_frequent_breakdowns(bot: Bot) -> None:
    """Alert when a bike has > N breakdowns in the last month."""
    max_count = settings.alert_breakdown_max_monthly
    month_ago = datetime.now() - timedelta(days=30)
    logger.debug("check_frequent_breakdowns: running (max={m})", m=max_count)

    async with market_session_maker() as session:
        # Group breakdowns by bike, filter for last 30 days
        result = await session.execute(
            select(
                BikeBreakdown.bike_id,
                func.count(BikeBreakdown.id).label("bd_count"),
            )
            .where(BikeBreakdown.reported_at >= month_ago)
            .group_by(BikeBreakdown.bike_id)
            .having(func.count(BikeBreakdown.id) > max_count),
        )
        rows = result.all()

        for bike_id, bd_count in rows:
            # Dedup
            if await _has_recent_alert(
                session, AlertType.FREQUENT_BREAKDOWNS, bike_id=bike_id,
            ):
                continue

            # Fetch bike info
            bike_result = await session.execute(
                select(Bike).where(Bike.id == bike_id),
            )
            bike = bike_result.scalar_one_or_none()
            if bike is None:
                continue

            store_name = bike.store.display_name if bike.store else "—"

            msg = (
                f"⚡ <b>Частые поломки</b>\n\n"
                f"🚲 <b>{bike.bike_number}</b> — {bike.model}\n"
                f"🏪 {store_name}\n"
                f"💥 Поломок за месяц: <b>{bd_count}</b> (порог: {max_count})\n\n"
                f"Рекомендуется проверка / списание!"
            )
            alert = BikeAlert(
                bike_id=bike.id,
                store_id=bike.store_id,
                alert_type=AlertType.FREQUENT_BREAKDOWNS,
                message=msg,
            )
            session.add(alert)
            await session.commit()

            await _send_alert(bot, msg)
            logger.info(
                "check_frequent_breakdowns: alert for bike {b} ({c} breakdowns)",
                b=bike.bike_number,
                c=bd_count,
            )
