"""Daily courier report delivery."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from html import escape
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from loguru import logger
from sqlalchemy import bindparam, select, text

from app.core.admin_access import get_admin_telegram_ids, is_admin_actor
from app.core.config import settings
from app.core.sla import get_sla_emoji, is_sla_eligible_layer, order_row_is_within_sla
from app.core.store_ids import parse_store_id_set
from app.core.tz import now_display
from app.db.base import market_session_maker
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.courier_shift import CourierShift
from app.db.models.store import Store

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from aiogram import Bot
    from aiogram.types import Message
    from sqlalchemy.ext.asyncio import AsyncSession


TELEGRAM_MESSAGE_SOFT_LIMIT = 3500
TEST_REPORT_COMMAND = "test_courier_report"

router = Router(name="daily_courier_report")


_REPORT_ORDERS_QUERY = text("""
    SELECT
        blco.admin_user_id AS admin_user_id,
        bod.store_id AS store_id,
        bod.id AS order_id,
        TIMESTAMPDIFF(MINUTE, bosc.accepted_at, bosc.completed_at) AS full_time_minutes,
        bdd.layer AS layer,
        bosc.completed_at AS completed_at
    FROM
        boom_link_couriers_orders blco
        INNER JOIN boom_order_details bod ON blco.order_id = bod.id
        INNER JOIN boom_orders_status_changes bosc ON bod.id = bosc.order_id
        LEFT JOIN boom_delivery_details bdd ON bod.id = bdd.order_id
    WHERE
        blco.admin_user_id IN :admin_user_ids
        AND bod.store_id IN :store_ids
        AND bod.type = 'customer'
        AND bod.status = 'completed'
        AND bosc.completed_at >= :completed_from
        AND bosc.completed_at < :completed_to
""").bindparams(
    bindparam("admin_user_ids", expanding=True),
    bindparam("store_ids", expanding=True),
)


@dataclass(frozen=True, slots=True)
class ReportOrderRow:
    admin_user_id: int
    store_id: int
    order_id: int
    completed_at: datetime
    full_time_minutes: int | None
    layer: int | None


@dataclass(frozen=True, slots=True)
class CourierReportRow:
    courier_id: int
    courier_name: str
    started_at: datetime
    total_orders: int
    sla_eligible_orders: int
    good_sla_orders: int

    @property
    def sla(self) -> float | None:
        if self.sla_eligible_orders == 0:
            return None
        return self.good_sla_orders / self.sla_eligible_orders * 100


@dataclass(frozen=True, slots=True)
class StoreReport:
    store_id: int
    store_name: str
    couriers: list[CourierReportRow]

    @property
    def total_couriers(self) -> int:
        return len(self.couriers)

    @property
    def total_orders(self) -> int:
        return sum(row.total_orders for row in self.couriers)

    @property
    def sla_eligible_orders(self) -> int:
        return sum(row.sla_eligible_orders for row in self.couriers)

    @property
    def good_sla_orders(self) -> int:
        return sum(row.good_sla_orders for row in self.couriers)

    @property
    def sla(self) -> float | None:
        if self.sla_eligible_orders == 0:
            return None
        return self.good_sla_orders / self.sla_eligible_orders * 100


@dataclass(frozen=True, slots=True)
class RecipientReportGroup:
    telegram_id: int
    recipient_kind: str
    reports: list[StoreReport]


@dataclass(slots=True)
class _CourierAccumulator:
    courier_id: int
    courier_name: str
    started_at: datetime
    total_orders: int = 0
    sla_eligible_orders: int = 0
    good_sla_orders: int = 0
    seen_order_ids: set[int] = field(default_factory=set)

    def add_shift_start(self, started_at: datetime) -> None:
        if started_at < self.started_at:
            self.started_at = started_at

    def add_order(self, order: ReportOrderRow) -> None:
        if order.order_id in self.seen_order_ids:
            return

        self.seen_order_ids.add(order.order_id)
        self.total_orders += 1

        if not is_sla_eligible_layer(order.layer):
            return

        self.sla_eligible_orders += 1
        if order_row_is_within_sla(order.full_time_minutes, order.layer):
            self.good_sla_orders += 1

    def to_report_row(self) -> CourierReportRow:
        return CourierReportRow(
            courier_id=self.courier_id,
            courier_name=self.courier_name,
            started_at=self.started_at,
            total_orders=self.total_orders,
            sla_eligible_orders=self.sla_eligible_orders,
            good_sla_orders=self.good_sla_orders,
        )


@dataclass(slots=True)
class _StoreAccumulator:
    store_id: int
    store_name: str
    couriers: dict[int, _CourierAccumulator] = field(default_factory=dict)


def _resolve_report_date(report_date: date | None = None) -> date:
    if report_date is not None:
        return report_date
    return now_display().date() - timedelta(days=1)


def _report_period(report_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(report_date, time.min)
    return start, start + timedelta(days=1)


def _parse_test_report_date(text: str | None) -> tuple[date | None, str | None]:
    if not text:
        return None, None

    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return None, None

    raw_date = parts[1].strip()
    try:
        return date.fromisoformat(raw_date), None
    except ValueError:
        return (
            None,
            "Дата должна быть в формате <code>YYYY-MM-DD</code>, "
            f"например <code>/{TEST_REPORT_COMMAND} 2026-04-21</code>.",
        )


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return int(value)
    if isinstance(value, str | bytes | bytearray):
        try:
            return int(value)
        except ValueError:
            return None

    try:
        return int(str(value))
    except ValueError:
        return None


def _admin_display_name(admin: AdminUser | None, admin_user_id: int) -> str:
    if admin is None:
        return str(admin_user_id)
    return f"{admin.name} {admin.surname or ''}".strip()


def _order_completed_in_shift(order: ReportOrderRow, shift: CourierShift) -> bool:
    if shift.shift_end is None:
        return False
    return shift.shift_start <= order.completed_at <= shift.shift_end


def _build_store_reports(
    stores: Sequence[Store],
    shifts: Sequence[CourierShift],
    admins_by_id: Mapping[int, AdminUser],
    order_rows: Sequence[ReportOrderRow],
) -> list[StoreReport]:
    store_accumulators = {
        store.id: _StoreAccumulator(store_id=store.id, store_name=store.display_name)
        for store in stores
    }
    visible_store_ids = set(store_accumulators)

    orders_by_courier: defaultdict[int, list[ReportOrderRow]] = defaultdict(list)
    for order in order_rows:
        orders_by_courier[order.admin_user_id].append(order)

    for shift in shifts:
        if shift.shift_end is None:
            continue

        shift_store_ids = parse_store_id_set(shift.store_ids) & visible_store_ids
        if not shift_store_ids:
            continue

        courier_id = shift.admin_user_id
        courier_name = _admin_display_name(admins_by_id.get(courier_id), courier_id)
        courier_orders = orders_by_courier.get(courier_id, [])

        for store_id in sorted(shift_store_ids):
            store_accumulator = store_accumulators[store_id]
            courier_accumulator = store_accumulator.couriers.get(courier_id)
            if courier_accumulator is None:
                courier_accumulator = _CourierAccumulator(
                    courier_id=courier_id,
                    courier_name=courier_name,
                    started_at=shift.shift_start,
                )
                store_accumulator.couriers[courier_id] = courier_accumulator
            else:
                courier_accumulator.add_shift_start(shift.shift_start)

            for order in courier_orders:
                if order.store_id != store_id:
                    continue
                if not _order_completed_in_shift(order, shift):
                    continue
                courier_accumulator.add_order(order)

    reports: list[StoreReport] = []
    for store in stores:
        accumulator = store_accumulators[store.id]
        couriers = [
            courier.to_report_row()
            for courier in sorted(
                accumulator.couriers.values(),
                key=lambda item: (item.started_at, item.courier_name),
            )
        ]
        reports.append(
            StoreReport(
                store_id=accumulator.store_id,
                store_name=accumulator.store_name,
                couriers=couriers,
            ),
        )
    return reports


async def _get_express_stores(session: AsyncSession) -> list[Store]:
    result = await session.execute(
        select(Store)
        .where(
            Store.main_id == "express",
            Store.id.notin_(settings.hidden_store_ids),
        )
        .order_by(Store.street),
    )
    return list(result.scalars().all())


async def _get_report_shifts(
    session: AsyncSession,
    *,
    day_start: datetime,
    day_end: datetime,
) -> list[CourierShift]:
    result = await session.execute(
        select(CourierShift)
        .where(
            CourierShift.shift_end.is_not(None),
            CourierShift.shift_end >= day_start,
            CourierShift.shift_end < day_end,
        )
        .order_by(CourierShift.shift_start),
    )
    return list(result.scalars().all())


async def _get_admin_users(
    session: AsyncSession,
    admin_user_ids: Iterable[int],
) -> dict[int, AdminUser]:
    ids = sorted(set(admin_user_ids))
    if not ids:
        return {}

    result = await session.execute(select(AdminUser).where(AdminUser.id.in_(ids)))
    admins = list(result.scalars().all())
    return {admin.id: admin for admin in admins}


async def _get_report_order_rows(
    session: AsyncSession,
    *,
    completed_from: datetime,
    completed_to: datetime,
    admin_user_ids: Iterable[int],
    store_ids: Iterable[int],
) -> list[ReportOrderRow]:
    courier_ids = sorted(set(admin_user_ids))
    visible_store_ids = sorted(set(store_ids))
    if not courier_ids or not visible_store_ids:
        return []

    result = await session.execute(
        _REPORT_ORDERS_QUERY,
        {
            "admin_user_ids": courier_ids,
            "store_ids": visible_store_ids,
            "completed_from": completed_from,
            "completed_to": completed_to,
        },
    )

    order_rows: list[ReportOrderRow] = []
    for row in result.mappings().all():
        completed_at = row.get("completed_at")
        if not isinstance(completed_at, datetime):
            continue

        admin_user_id = _coerce_optional_int(row.get("admin_user_id"))
        store_id = _coerce_optional_int(row.get("store_id"))
        order_id = _coerce_optional_int(row.get("order_id"))
        if admin_user_id is None or store_id is None or order_id is None:
            continue

        order_rows.append(
            ReportOrderRow(
                admin_user_id=admin_user_id,
                store_id=store_id,
                order_id=order_id,
                completed_at=completed_at,
                full_time_minutes=_coerce_optional_int(row.get("full_time_minutes")),
                layer=_coerce_optional_int(row.get("layer")),
            ),
        )

    return order_rows


async def _load_store_reports(
    session: AsyncSession,
    report_date: date,
) -> list[StoreReport]:
    day_start, day_end = _report_period(report_date)
    stores = await _get_express_stores(session)
    shifts = await _get_report_shifts(session, day_start=day_start, day_end=day_end)
    admin_user_ids = {shift.admin_user_id for shift in shifts}
    admins_by_id = await _get_admin_users(session, admin_user_ids)

    completed_from = min(shift.shift_start for shift in shifts) if shifts else day_start

    order_rows = await _get_report_order_rows(
        session,
        completed_from=completed_from,
        completed_to=day_end,
        admin_user_ids=admin_user_ids,
        store_ids=[store.id for store in stores],
    )
    return _build_store_reports(stores, shifts, admins_by_id, order_rows)


async def _get_supervisors(session: AsyncSession) -> list[BotUser]:
    result = await session.execute(
        select(BotUser).where(BotUser.role == UserRole.SUPERVISOR).order_by(BotUser.id),
    )
    return list(result.scalars().all())


def _build_recipient_report_groups(
    admin_telegram_ids: Iterable[int],
    supervisors: Iterable[BotUser],
    reports: Sequence[StoreReport],
) -> list[RecipientReportGroup]:
    groups: list[RecipientReportGroup] = []
    admin_seen: set[int] = set()

    for telegram_id in admin_telegram_ids:
        if telegram_id in admin_seen:
            continue
        admin_seen.add(telegram_id)
        groups.append(
            RecipientReportGroup(
                telegram_id=telegram_id,
                recipient_kind="admin",
                reports=list(reports),
            ),
        )

    for supervisor in supervisors:
        if supervisor.telegram_id in admin_seen:
            continue

        supervisor_store_ids = set(supervisor.assigned_store_ids)
        supervisor_reports = [
            report for report in reports if report.store_id in supervisor_store_ids
        ]
        if not supervisor_reports:
            continue

        groups.append(
            RecipientReportGroup(
                telegram_id=supervisor.telegram_id,
                recipient_kind="supervisor",
                reports=supervisor_reports,
            ),
        )

    return groups


def _format_sla_html(sla: float | None) -> str:
    if sla is None:
        return "<b>—</b>"
    return f"<b>{sla:.1f}%</b> {get_sla_emoji(sla)}"


def _format_store_summary_lines(
    report: StoreReport,
    report_date: date,
    *,
    continuation: bool = False,
) -> list[str]:
    title = "📊 <b>Отчет по курьерам</b>"
    if continuation:
        title += " (продолжение)"

    return [
        title,
        f"Дата: <b>{report_date:%d.%m.%Y}</b>",
        f"Склад: <b>{escape(report.store_name)}</b>",
        "",
        f"Курьеров: <b>{report.total_couriers}</b>",
        f"Заказов: <b>{report.total_orders}</b>",
        f"SLA общий: {_format_sla_html(report.sla)}",
    ]


def _format_courier_lines(row: CourierReportRow) -> list[str]:
    return [
        f"Имя: <b>{escape(row.courier_name)}</b>",
        f"Начал смену: <b>{row.started_at:%H:%M}</b>",
        f"Заказов: <b>{row.total_orders}</b>",
        f"SLA: {_format_sla_html(row.sla)}",
    ]


def _format_store_report_messages(
    report: StoreReport,
    report_date: date,
    *,
    max_length: int = TELEGRAM_MESSAGE_SOFT_LIMIT,
) -> list[str]:
    base_lines = _format_store_summary_lines(report, report_date)
    if not report.couriers:
        return ["\n".join([*base_lines, "", "<i>Закрытых смен за день нет.</i>"])]

    messages: list[str] = []
    current_lines = [*base_lines, "", "<b>Курьеры:</b>"]
    first_block_in_message = True

    for row in report.couriers:
        block = _format_courier_lines(row)
        separator = [] if first_block_in_message else [""]
        candidate_lines = [*current_lines, *separator, *block]
        candidate = "\n".join(candidate_lines)

        if len(candidate) > max_length and not first_block_in_message:
            messages.append("\n".join(current_lines))
            current_lines = [
                *_format_store_summary_lines(report, report_date, continuation=True),
                "",
                "<b>Курьеры:</b>",
                *block,
            ]
        else:
            current_lines = candidate_lines

        first_block_in_message = False

    messages.append("\n".join(current_lines))
    return messages


async def _send_direct_report(
    bot: Bot,
    telegram_id: int,
    message: str,
    *,
    recipient_kind: str,
) -> None:
    try:
        await bot.send_message(chat_id=telegram_id, text=message)
        logger.info(
            "Daily courier report sent to {kind} {telegram_id}",
            kind=recipient_kind,
            telegram_id=telegram_id,
        )
    except Exception:
        logger.exception(
            "Failed to send daily courier report to {kind} {telegram_id}",
            kind=recipient_kind,
            telegram_id=telegram_id,
        )


async def send_daily_courier_report(
    bot: Bot,
    report_date: date | None = None,
) -> None:
    """Send daily courier reports for the previous Yakutsk calendar day."""
    resolved_report_date = _resolve_report_date(report_date)
    logger.debug(
        "send_daily_courier_report: running for {date}",
        date=resolved_report_date.isoformat(),
    )

    async with market_session_maker() as session:
        reports = await _load_store_reports(session, resolved_report_date)
        admin_recipients = await get_admin_telegram_ids(session)
        supervisors = await _get_supervisors(session)

    recipient_groups = _build_recipient_report_groups(
        admin_recipients,
        supervisors,
        reports,
    )

    message_count = 0
    for group in recipient_groups:
        for report in group.reports:
            for message in _format_store_report_messages(report, resolved_report_date):
                await _send_direct_report(
                    bot,
                    group.telegram_id,
                    message,
                    recipient_kind=group.recipient_kind,
                )
                message_count += 1

    logger.info(
        "send_daily_courier_report: sent {messages} messages for {stores} stores "
        "to {recipients} recipients",
        messages=message_count,
        stores=len(reports),
        recipients=len(recipient_groups),
    )


async def send_daily_courier_report_to_chat(
    bot: Bot,
    chat_id: int,
    report_date: date | None = None,
) -> int:
    """Send all daily courier reports to one chat for a production smoke test."""
    resolved_report_date = _resolve_report_date(report_date)

    async with market_session_maker() as session:
        reports = await _load_store_reports(session, resolved_report_date)

    message_count = 0
    for store_report in reports:
        for message in _format_store_report_messages(store_report, resolved_report_date):
            await _send_direct_report(
                bot,
                chat_id,
                message,
                recipient_kind="test_admin",
            )
            message_count += 1

    logger.info(
        "send_daily_courier_report_to_chat: sent {messages} messages for {stores} "
        "stores to chat {chat_id}",
        messages=message_count,
        stores=len(reports),
        chat_id=chat_id,
    )
    return message_count


@router.message(Command(TEST_REPORT_COMMAND))
async def cmd_test_courier_report(
    message: Message,
    bot_user: BotUser | None = None,
) -> None:
    """Admin-only command for sending the daily report to the current chat."""
    if message.from_user is None:
        return

    if not is_admin_actor(bot_user, message.from_user.id):
        await message.answer("⛔ Команда доступна только админам.")
        return

    requested_report_date, error = _parse_test_report_date(message.text)
    if error is not None:
        await message.answer(error)
        return

    resolved_report_date = _resolve_report_date(requested_report_date)
    await message.answer(
        "Собираю тестовый отчет за "
        f"<b>{resolved_report_date:%d.%m.%Y}</b>.\n"
        "Отправлю только в этот чат.",
    )

    if message.bot is None:
        logger.warning("test courier report command has no bot bound to message")
        await message.answer("Не удалось отправить отчет: bot не привязан к сообщению.")
        return

    sent_messages = await send_daily_courier_report_to_chat(
        message.bot,
        message.chat.id,
        resolved_report_date,
    )
    await message.answer(f"Готово. Отправлено сообщений: <b>{sent_messages}</b>.")
