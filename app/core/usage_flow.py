from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.display import MISSING_LABEL, bike_label, display_name_label
from app.core.store_access import apply_store_scope
from app.core.tz import to_yakutsk
from app.db.models.admin_user import AdminUser
from app.db.models.bike import Bike
from app.db.models.bike_usage_log import BikeUsageLog
from app.db.models.store import Store

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.bot_user import BotUser


@dataclass(frozen=True)
class TakeBikeDraft:
    bike_id: int
    courier_id: int
    store_id: int


@dataclass(frozen=True)
class TakeBikeConfirmation:
    draft: TakeBikeDraft
    bike_label: str
    courier_label: str
    store_label: str


@dataclass(frozen=True)
class UsageShiftSummary:
    log_id: int
    bike_number: str
    bike_model: str
    courier_name: str
    store_name: str
    started_at: datetime
    ended_at: datetime | None = None

    @property
    def bike_label(self) -> str:
        return f"{self.bike_number} — {self.bike_model}" if self.bike_model else self.bike_number


async def build_take_bike_confirmation(
    session: AsyncSession,
    draft: TakeBikeDraft,
    bot_user: BotUser | None,
) -> TakeBikeConfirmation:
    """Load the display data for the take-bike confirmation phase."""
    bike = await session.get(Bike, draft.bike_id)
    courier = await session.get(AdminUser, draft.courier_id)
    store_result = await session.execute(
        apply_store_scope(
            select(Store).where(Store.id == draft.store_id),
            Store.id,
            bot_user,
        ),
    )
    store = store_result.scalar_one_or_none()

    return TakeBikeConfirmation(
        draft=draft,
        bike_label=bike_label(bike),
        courier_label=display_name_label(courier),
        store_label=display_name_label(store),
    )


def create_usage_log(
    draft: TakeBikeDraft,
    *,
    started_at: datetime | None = None,
) -> BikeUsageLog:
    """Create a usage-log entity from a validated take-bike draft."""
    return BikeUsageLog(
        bike_id=draft.bike_id,
        courier_id=draft.courier_id,
        store_id=draft.store_id,
        started_at=started_at or datetime.now(),
    )


def usage_shift_summary(log: BikeUsageLog) -> UsageShiftSummary:
    bike = log.bike
    courier = log.courier
    store = log.store

    return UsageShiftSummary(
        log_id=log.id,
        bike_number=bike.bike_number if bike else MISSING_LABEL,
        bike_model=bike.model if bike else "",
        courier_name=display_name_label(courier),
        store_name=display_name_label(store),
        started_at=log.started_at,
        ended_at=log.ended_at,
    )


def active_usage_log_query(
    store_id: int,
    bot_user: BotUser | None,
) -> Any:
    query = apply_store_scope(
        select(BikeUsageLog)
        .options(
            selectinload(BikeUsageLog.bike),
            selectinload(BikeUsageLog.courier),
            selectinload(BikeUsageLog.store),
        )
        .where(BikeUsageLog.ended_at.is_(None))
        .order_by(BikeUsageLog.started_at.desc()),
        BikeUsageLog.store_id,
        bot_user,
    )
    if store_id > 0:
        query = query.where(BikeUsageLog.store_id == store_id)
    return query


async def list_active_usage_logs(
    session: AsyncSession,
    *,
    store_id: int,
    bot_user: BotUser | None,
) -> list[BikeUsageLog]:
    result = await session.execute(active_usage_log_query(store_id, bot_user))
    return list(result.scalars().all())


async def get_active_usage_log(
    session: AsyncSession,
    *,
    log_id: int,
    bot_user: BotUser | None,
) -> BikeUsageLog | None:
    result = await session.execute(
        apply_store_scope(
            select(BikeUsageLog)
            .options(
                selectinload(BikeUsageLog.bike),
                selectinload(BikeUsageLog.courier),
                selectinload(BikeUsageLog.store),
            )
            .where(BikeUsageLog.id == log_id),
            BikeUsageLog.store_id,
            bot_user,
        ),
    )
    log = cast("BikeUsageLog | None", result.scalar_one_or_none())
    if log is None or log.ended_at is not None:
        return None
    return log


async def finish_usage_log(
    session: AsyncSession,
    *,
    log_id: int,
    bot_user: BotUser | None,
    ended_at: datetime | None = None,
) -> UsageShiftSummary | None:
    log = await get_active_usage_log(session, log_id=log_id, bot_user=bot_user)
    if log is None:
        return None

    log.ended_at = ended_at or datetime.now()
    return usage_shift_summary(log)


def format_active_shift_lines(summaries: list[UsageShiftSummary]) -> list[str]:
    lines = ["👀 <b>Активные смены</b>", f"Всего: {len(summaries)}", ""]
    for summary in summaries:
        started = to_yakutsk(summary.started_at).strftime("%d.%m %H:%M")
        lines.append(
            f"🚲 <b>{summary.bike_number}</b> {summary.bike_model}\n"
            f"   👤 {summary.courier_name} • 🏪 {summary.store_name}\n"
            f"   🕐 с {started}\n",
        )
    return lines
