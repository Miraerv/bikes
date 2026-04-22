from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from app.bot.handlers import daily_courier_report as report
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.courier_shift import CourierShift
from app.db.models.store import Store

if TYPE_CHECKING:
    import pytest


def _store(store_id: int, name: str) -> Store:
    return Store(id=store_id, title=name, street=name, main_id="express")


def _admin(admin_user_id: int, name: str) -> AdminUser:
    return AdminUser(
        id=admin_user_id,
        name=name,
        surname=None,
        email=f"{admin_user_id}@example.test",
    )


def _shift(
    *,
    admin_user_id: int,
    store_ids: str,
    start: datetime,
    end: datetime | None,
) -> CourierShift:
    return CourierShift(
        id=admin_user_id,
        admin_user_id=admin_user_id,
        store_ids=store_ids,
        status="offline",
        shift_start=start,
        shift_end=end,
    )


def _order(
    *,
    admin_user_id: int,
    store_id: int,
    order_id: int,
    completed_at: datetime,
    full_time_minutes: int | None,
    layer: int | None,
) -> report.ReportOrderRow:
    return report.ReportOrderRow(
        admin_user_id=admin_user_id,
        store_id=store_id,
        order_id=order_id,
        completed_at=completed_at,
        full_time_minutes=full_time_minutes,
        layer=layer,
    )


def _supervisor(telegram_id: int, store_ids: list[int]) -> BotUser:
    user = BotUser(
        telegram_id=telegram_id,
        name=f"Supervisor {telegram_id}",
        role=UserRole.SUPERVISOR,
    )
    user.set_assigned_store_ids(store_ids)
    return user


def test_resolve_report_date_defaults_to_previous_yakutsk_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(report, "now_display", lambda: datetime(2026, 4, 22, 0, 0))

    assert report._resolve_report_date() == date(2026, 4, 21)
    assert report._resolve_report_date(date(2026, 4, 20)) == date(2026, 4, 20)


def test_build_store_reports_aggregates_couriers_orders_and_sla() -> None:
    stores = [_store(54, "Чиряева")]
    shifts = [
        _shift(
            admin_user_id=1,
            store_ids="[54]",
            start=datetime(2026, 4, 21, 16, 10),
            end=datetime(2026, 4, 21, 23, 0),
        ),
        _shift(
            admin_user_id=2,
            store_ids="[54]",
            start=datetime(2026, 4, 21, 17, 0),
            end=datetime(2026, 4, 21, 22, 0),
        ),
    ]
    orders = [
        _order(
            admin_user_id=1,
            store_id=54,
            order_id=100,
            completed_at=datetime(2026, 4, 21, 18, 0),
            full_time_minutes=40,
            layer=1,
        ),
        _order(
            admin_user_id=1,
            store_id=54,
            order_id=101,
            completed_at=datetime(2026, 4, 21, 19, 0),
            full_time_minutes=50,
            layer=1,
        ),
        _order(
            admin_user_id=1,
            store_id=54,
            order_id=102,
            completed_at=datetime(2026, 4, 21, 20, 0),
            full_time_minutes=10,
            layer=None,
        ),
    ]

    reports = report._build_store_reports(
        stores,
        shifts,
        {1: _admin(1, "Ivan"), 2: _admin(2, "Petr")},
        orders,
    )

    store_report = reports[0]
    assert store_report.total_couriers == 2
    assert store_report.total_orders == 3
    assert store_report.sla == 50.0
    assert [(row.courier_name, row.total_orders, row.sla) for row in store_report.couriers] == [
        ("Ivan", 3, 50.0),
        ("Petr", 0, None),
    ]


def test_multi_store_shift_counts_orders_by_order_store() -> None:
    stores = [_store(54, "First"), _store(55, "Second")]
    shifts = [
        _shift(
            admin_user_id=1,
            store_ids='[54, "55"]',
            start=datetime(2026, 4, 21, 8, 0),
            end=datetime(2026, 4, 21, 18, 0),
        ),
    ]
    orders = [
        _order(
            admin_user_id=1,
            store_id=54,
            order_id=100,
            completed_at=datetime(2026, 4, 21, 10, 0),
            full_time_minutes=30,
            layer=1,
        ),
        _order(
            admin_user_id=1,
            store_id=55,
            order_id=101,
            completed_at=datetime(2026, 4, 21, 11, 0),
            full_time_minutes=30,
            layer=2,
        ),
    ]

    reports = report._build_store_reports(stores, shifts, {1: _admin(1, "Ivan")}, orders)

    assert [store_report.total_couriers for store_report in reports] == [1, 1]
    assert [store_report.total_orders for store_report in reports] == [1, 1]
    assert [store_report.couriers[0].courier_name for store_report in reports] == [
        "Ivan",
        "Ivan",
    ]


def test_build_recipient_report_groups_routes_admins_and_supervisors() -> None:
    reports = [
        report.StoreReport(store_id=54, store_name="First", couriers=[]),
        report.StoreReport(store_id=55, store_name="Second", couriers=[]),
    ]
    groups = report._build_recipient_report_groups(
        [100, 100],
        [_supervisor(200, [54, 55]), _supervisor(201, [99])],
        reports,
    )

    assert [(group.telegram_id, group.recipient_kind) for group in groups] == [
        (100, "admin"),
        (200, "supervisor"),
    ]
    assert [[store_report.store_id for store_report in group.reports] for group in groups] == [
        [54, 55],
        [54, 55],
    ]


def test_format_store_report_messages_splits_long_courier_lists() -> None:
    rows = [
        report.CourierReportRow(
            courier_id=item,
            courier_name=f"Courier {item}",
            started_at=datetime(2026, 4, 21, 8, item),
            total_orders=10,
            sla_eligible_orders=10,
            good_sla_orders=10,
        )
        for item in range(5)
    ]
    store_report = report.StoreReport(store_id=54, store_name="First", couriers=rows)

    messages = report._format_store_report_messages(
        store_report,
        date(2026, 4, 21),
        max_length=300,
    )

    assert len(messages) > 1
    assert all("Отчет по курьерам" in message for message in messages)
