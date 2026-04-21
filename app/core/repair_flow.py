from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.store_access import apply_store_scope
from app.core.tz import to_yakutsk
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_breakdown import BikeBreakdown
from app.db.models.bike_repair import BikeRepair
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.store import Store

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class RepairPickupDraft:
    bike_id: int
    store_id: int
    breakdown_id: int | None
    mechanic_id: int | None
    mechanic_name: str | None


@dataclass(frozen=True)
class RepairPickupConfirmation:
    draft: RepairPickupDraft
    bike_label: str
    store_label: str
    mechanic_name: str
    breakdown_type: str | None
    breakdown_reported_at: datetime | None


@dataclass(frozen=True)
class RepairCompletionDraft:
    repair_id: int
    work_description: str | None
    repair_duration_minutes: int | None
    cost: Decimal | None


@dataclass(frozen=True)
class RepairCompletionConfirmation:
    draft: RepairCompletionDraft
    bike_label: str
    mechanic_name: str
    work_description_label: str
    duration_label: str
    cost_label: str


@dataclass(frozen=True)
class SavedRepairCompletion:
    repair: BikeRepair
    bike_status_changed: bool


def parse_repair_duration(text: str) -> int | None:
    """Parse optional repair duration entered in minutes."""
    cleaned = text.strip()
    if cleaned == "-":
        return None
    try:
        duration = int(cleaned)
    except ValueError as exc:
        raise ValueError("duration_must_be_integer") from exc

    if duration <= 0:
        raise ValueError("duration_must_be_positive")
    return duration


def parse_repair_cost(text: str) -> Decimal | None:
    """Parse optional repair cost."""
    cleaned = text.strip()
    if cleaned == "-":
        return None
    try:
        cost = Decimal(cleaned.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("cost_must_be_decimal") from exc

    if cost < 0:
        raise ValueError("cost_must_not_be_negative")
    return cost


async def list_open_breakdowns(
    session: AsyncSession,
    *,
    bike_id: int,
    limit: int = 10,
) -> list[BikeBreakdown]:
    result = await session.execute(
        select(BikeBreakdown)
        .where(BikeBreakdown.bike_id == bike_id)
        .order_by(BikeBreakdown.reported_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


async def list_mechanics(session: AsyncSession) -> list[BotUser]:
    result = await session.execute(
        select(BotUser)
        .where(BotUser.role == UserRole.MECHANIC)
        .order_by(BotUser.name),
    )
    return list(result.scalars().all())


async def build_pickup_confirmation(
    session: AsyncSession,
    draft: RepairPickupDraft,
) -> RepairPickupConfirmation:
    """Load display data for the repair pickup confirmation phase."""
    bike = await session.get(Bike, draft.bike_id)
    store_result = await session.execute(
        select(Store).where(Store.id == draft.store_id),
    )
    store = store_result.scalar_one_or_none()

    breakdown_type = None
    breakdown_reported_at = None
    if draft.breakdown_id:
        breakdown = await session.get(BikeBreakdown, draft.breakdown_id)
        if breakdown:
            breakdown_type = breakdown.breakdown_type.value
            breakdown_reported_at = breakdown.reported_at

    return RepairPickupConfirmation(
        draft=draft,
        bike_label=f"{bike.bike_number} — {bike.model}" if bike else "—",
        store_label=store.display_name if store else "—",
        mechanic_name=draft.mechanic_name or "—",
        breakdown_type=breakdown_type,
        breakdown_reported_at=breakdown_reported_at,
    )


def create_repair_pickup(
    draft: RepairPickupDraft,
    *,
    picked_up_at: datetime | None = None,
) -> BikeRepair:
    return BikeRepair(
        bike_id=draft.bike_id,
        breakdown_id=draft.breakdown_id,
        mechanic_id=draft.mechanic_id,
        mechanic_name=draft.mechanic_name,
        store_id=draft.store_id,
        picked_up_at=picked_up_at or datetime.now(),
    )


async def save_repair_pickup(
    session: AsyncSession,
    draft: RepairPickupDraft,
    *,
    picked_up_at: datetime | None = None,
) -> BikeRepair:
    repair = create_repair_pickup(draft, picked_up_at=picked_up_at)
    session.add(repair)

    bike = await session.get(Bike, draft.bike_id)
    if bike and bike.status != BikeStatus.REPAIR:
        bike.status = BikeStatus.REPAIR

    return repair


async def build_completion_confirmation(
    session: AsyncSession,
    draft: RepairCompletionDraft,
    bot_user: BotUser | None,
) -> RepairCompletionConfirmation | None:
    """Load display data for the repair completion confirmation phase."""
    result = await session.execute(
        apply_store_scope(
            select(BikeRepair)
            .options(selectinload(BikeRepair.bike))
            .where(BikeRepair.id == draft.repair_id),
            BikeRepair.store_id,
            bot_user,
        ),
    )
    repair = result.scalar_one_or_none()
    if repair is None:
        return None

    bike = repair.bike
    duration = draft.repair_duration_minutes
    cost = draft.cost

    return RepairCompletionConfirmation(
        draft=draft,
        bike_label=f"{bike.bike_number} — {bike.model}" if bike else "—",
        mechanic_name=repair.mechanic_name or "—",
        work_description_label=draft.work_description or "—",
        duration_label=f"{duration} мин." if duration else "—",
        cost_label=f"{cost} ₽" if cost else "—",
    )


async def save_repair_completion(
    session: AsyncSession,
    draft: RepairCompletionDraft,
    bot_user: BotUser | None,
    *,
    completed_at: datetime | None = None,
) -> SavedRepairCompletion | None:
    result = await session.execute(
        apply_store_scope(
            select(BikeRepair).where(BikeRepair.id == draft.repair_id),
            BikeRepair.store_id,
            bot_user,
        ),
    )
    repair = result.scalar_one_or_none()
    if repair is None:
        return None

    repair.completed_at = completed_at or datetime.now()
    repair.work_description = draft.work_description
    repair.repair_duration_minutes = draft.repair_duration_minutes
    repair.cost = draft.cost

    bike = await session.get(Bike, repair.bike_id)
    bike_status_changed = False
    if bike and bike.status == BikeStatus.REPAIR:
        bike.status = BikeStatus.ONLINE
        bike_status_changed = True

    return SavedRepairCompletion(
        repair=repair,
        bike_status_changed=bike_status_changed,
    )


def format_pickup_breakdown_label(
    confirmation: RepairPickupConfirmation,
    type_labels: dict[str, str],
    type_emojis: dict[str, str],
) -> str:
    if confirmation.breakdown_type is None:
        return "— (без привязки)"

    bd_type = confirmation.breakdown_type
    bd_emoji = type_emojis.get(bd_type, "❓")
    bd_type_label = type_labels.get(bd_type, bd_type)
    reported = (
        to_yakutsk(confirmation.breakdown_reported_at).strftime("%d.%m.%Y")
        if confirmation.breakdown_reported_at
        else "—"
    )
    return f"{bd_emoji} {bd_type_label} ({reported})"
