from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.display import bike_label, display_name_label, optional_text_label
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_breakdown import BikeBreakdown, BreakdownType
from app.db.models.bike_breakdown_photo import BikeBreakdownPhoto
from app.db.models.bike_usage_log import BikeUsageLog
from app.db.models.store import Store

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class BreakdownCourier:
    courier_id: int
    courier_name: str


@dataclass(frozen=True)
class BreakdownDraft:
    bike_id: int
    store_id: int
    breakdown_type: str
    description: str | None
    photo_ids: tuple[str, ...]
    courier_id: int
    courier_name: str


@dataclass(frozen=True)
class BreakdownConfirmation:
    draft: BreakdownDraft
    bike_label: str
    store_label: str
    description_label: str
    photo_count: int


@dataclass(frozen=True)
class CreatedBreakdown:
    breakdown_id: int
    bike_status_changed: bool


async def detect_last_usage_courier(
    session: AsyncSession,
    *,
    bike_id: int,
) -> BreakdownCourier | None:
    """Find the last courier from usage logs for the selected bike."""
    result = await session.execute(
        select(BikeUsageLog)
        .options(selectinload(BikeUsageLog.courier))
        .where(BikeUsageLog.bike_id == bike_id)
        .order_by(BikeUsageLog.started_at.desc())
        .limit(1),
    )
    last_log = result.scalar_one_or_none()
    if last_log is None or not last_log.courier_id:
        return None

    return BreakdownCourier(
        courier_id=last_log.courier_id,
        courier_name=display_name_label(last_log.courier),
    )


async def build_breakdown_confirmation(
    session: AsyncSession,
    draft: BreakdownDraft,
) -> BreakdownConfirmation:
    """Load display data for the breakdown confirmation phase."""
    bike = await session.get(Bike, draft.bike_id)
    store_result = await session.execute(
        select(Store).where(Store.id == draft.store_id),
    )
    store = store_result.scalar_one_or_none()

    return BreakdownConfirmation(
        draft=draft,
        bike_label=bike_label(bike),
        store_label=display_name_label(store),
        description_label=optional_text_label(draft.description),
        photo_count=len(draft.photo_ids),
    )


def create_breakdown(
    draft: BreakdownDraft,
    *,
    reported_at: datetime | None = None,
) -> BikeBreakdown:
    """Create a breakdown entity from a validated draft."""
    return BikeBreakdown(
        bike_id=draft.bike_id,
        courier_id=draft.courier_id,
        store_id=draft.store_id,
        reported_by=draft.courier_id,
        breakdown_type=BreakdownType(draft.breakdown_type),
        description=draft.description,
        reported_at=reported_at or datetime.now(),
    )


async def save_breakdown(
    session: AsyncSession,
    draft: BreakdownDraft,
    *,
    reported_at: datetime | None = None,
) -> CreatedBreakdown:
    """Persist a breakdown, its photos, and the bike status transition."""
    breakdown = create_breakdown(draft, reported_at=reported_at)
    session.add(breakdown)
    await session.flush()

    for file_id in draft.photo_ids:
        session.add(BikeBreakdownPhoto(
            breakdown_id=breakdown.id,
            photo_url=file_id,
        ))

    status_changed = False
    bike = await session.get(Bike, draft.bike_id)
    if bike and bike.status == BikeStatus.ONLINE:
        bike.status = BikeStatus.INSPECTION
        status_changed = True

    return CreatedBreakdown(
        breakdown_id=breakdown.id,
        bike_status_changed=status_changed,
    )
