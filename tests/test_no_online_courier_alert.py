# ruff: noqa: S101

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.bot.handlers import alerts
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.courier_shift import CourierShift
from app.db.models.store import Store


class _FakeSession:
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:
        return None


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.calls.append((chat_id, text))


def _store(store_id: int, name: str) -> Store:
    return Store(id=store_id, title=name, street=name, main_id="express")


def _shift(
    *,
    status: str,
    store_ids: str,
    start: datetime,
    end: datetime | None = None,
) -> CourierShift:
    return CourierShift(
        id=1,
        admin_user_id=1,
        status=status,
        store_ids=store_ids,
        shift_start=start,
        shift_end=end,
    )


def test_find_stores_without_online_courier_requires_active_online_shift() -> None:
    control_ts = datetime(2026, 4, 21, 8, 15)
    stores = [
        _store(54, "Covered"),
        _store(55, "Offline"),
        _store(56, "Ended"),
        _store(57, "Missing"),
    ]
    shifts = [
        _shift(
            status="online",
            store_ids="[54]",
            start=datetime(2026, 4, 21, 8, 0),
        ),
        _shift(
            status="offline",
            store_ids="[55]",
            start=datetime(2026, 4, 21, 8, 0),
        ),
        _shift(
            status="online",
            store_ids="[56]",
            start=datetime(2026, 4, 21, 7, 0),
            end=control_ts,
        ),
    ]

    incident_stores = alerts._find_stores_without_online_courier(
        stores,
        shifts,
        control_ts=control_ts,
    )

    assert [store.id for store in incident_stores] == [55, 56, 57]


def test_multi_store_online_shift_covers_all_store_ids() -> None:
    control_ts = datetime(2026, 4, 21, 8, 15)
    stores = [_store(54, "First"), _store(55, "Second"), _store(56, "Third")]
    shifts = [
        _shift(
            status="online",
            store_ids='[54, "55"]',
            start=datetime(2026, 4, 21, 7, 30),
        ),
    ]

    incident_stores = alerts._find_stores_without_online_courier(
        stores,
        shifts,
        control_ts=control_ts,
    )

    assert [store.id for store in incident_stores] == [56]


def test_group_supervisor_incidents_filters_to_assigned_stores() -> None:
    incident_stores = [_store(54, "First"), _store(55, "Second"), _store(56, "Third")]
    supervisor = BotUser(
        telegram_id=900,
        name="Supervisor",
        role=UserRole.SUPERVISOR,
    )
    supervisor.set_assigned_store_ids([54, 55])
    unrelated_supervisor = BotUser(
        telegram_id=901,
        name="Other Supervisor",
        role=UserRole.SUPERVISOR,
    )
    unrelated_supervisor.set_assigned_store_ids([99])

    groups = alerts._group_supervisor_incidents(
        [supervisor, unrelated_supervisor],
        incident_stores,
    )

    assert [
        (telegram_id, [store.id for store in stores])
        for telegram_id, stores in groups
    ] == [
        (900, [54, 55]),
    ]


@pytest.mark.asyncio
async def test_check_no_online_couriers_routes_admin_and_supervisor_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control_ts = datetime(2026, 4, 21, 8, 15)
    stores = [_store(54, "First"), _store(55, "Second"), _store(56, "Covered")]
    shifts = [
        _shift(
            status="online",
            store_ids="[56]",
            start=datetime(2026, 4, 21, 8, 0),
        ),
    ]

    async def fake_get_express_stores(_session: object) -> list[Store]:
        return stores

    async def fake_get_control_time_courier_shifts(
        _session: object,
        **_kwargs: object,
    ) -> list[CourierShift]:
        return shifts

    async def fake_get_admin_telegram_ids(_session: object) -> list[int]:
        return [100, 101]

    async def fake_get_supervisor_incident_groups(
        _session: object,
        incident_stores: list[Store],
    ) -> list[tuple[int, list[Store]]]:
        return [(200, [incident_stores[0]])]

    monkeypatch.setattr(alerts, "market_session_maker", lambda: _FakeSession())
    monkeypatch.setattr(alerts, "_get_express_stores", fake_get_express_stores)
    monkeypatch.setattr(
        alerts,
        "_get_control_time_courier_shifts",
        fake_get_control_time_courier_shifts,
    )
    monkeypatch.setattr(alerts, "get_admin_telegram_ids", fake_get_admin_telegram_ids)
    monkeypatch.setattr(
        alerts,
        "_get_supervisor_incident_groups",
        fake_get_supervisor_incident_groups,
    )

    bot = _FakeBot()
    await alerts.check_no_online_couriers(bot, "08:15", control_ts=control_ts)

    assert [chat_id for chat_id, _text in bot.calls] == [100, 101, 200]
    assert "First (id: 54)" in bot.calls[0][1]
    assert "Second (id: 55)" in bot.calls[0][1]
    assert "Covered (id: 56)" not in bot.calls[0][1]
    assert "First (id: 54)" in bot.calls[2][1]
    assert "Second (id: 55)" not in bot.calls[2][1]


@pytest.mark.asyncio
async def test_check_no_online_couriers_sends_each_slot_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control_ts = datetime(2026, 4, 21, 8, 15)
    stores = [_store(54, "First")]

    async def fake_get_express_stores(_session: object) -> list[Store]:
        return stores

    async def fake_get_control_time_courier_shifts(
        _session: object,
        **_kwargs: object,
    ) -> list[CourierShift]:
        return []

    async def fake_get_admin_telegram_ids(_session: object) -> list[int]:
        return [100]

    async def fake_get_supervisor_incident_groups(
        _session: object,
        _incident_stores: list[Store],
    ) -> list[tuple[int, list[Store]]]:
        return []

    monkeypatch.setattr(alerts, "market_session_maker", lambda: _FakeSession())
    monkeypatch.setattr(alerts, "_get_express_stores", fake_get_express_stores)
    monkeypatch.setattr(
        alerts,
        "_get_control_time_courier_shifts",
        fake_get_control_time_courier_shifts,
    )
    monkeypatch.setattr(alerts, "get_admin_telegram_ids", fake_get_admin_telegram_ids)
    monkeypatch.setattr(
        alerts,
        "_get_supervisor_incident_groups",
        fake_get_supervisor_incident_groups,
    )

    bot = _FakeBot()
    await alerts.check_no_online_couriers(bot, "08:15", control_ts=control_ts)
    await alerts.check_no_online_couriers(
        bot,
        "16:15",
        control_ts=control_ts.replace(hour=16),
    )

    assert len(bot.calls) == 2
    assert "Слот: <b>08:15</b>" in bot.calls[0][1]
    assert "Слот: <b>16:15</b>" in bot.calls[1][1]


@pytest.mark.asyncio
async def test_check_no_online_couriers_keeps_admin_branch_when_supervisors_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control_ts = datetime(2026, 4, 21, 8, 15)
    stores = [_store(54, "First")]

    async def fake_get_express_stores(_session: object) -> list[Store]:
        return stores

    async def fake_get_control_time_courier_shifts(
        _session: object,
        **_kwargs: object,
    ) -> list[CourierShift]:
        return []

    async def fake_get_admin_telegram_ids(_session: object) -> list[int]:
        return [100]

    async def fake_get_supervisor_incident_groups(
        _session: object,
        _incident_stores: list[Store],
    ) -> list[tuple[int, list[Store]]]:
        raise SQLAlchemyError("missing store_ids")

    monkeypatch.setattr(alerts, "market_session_maker", lambda: _FakeSession())
    monkeypatch.setattr(alerts, "_get_express_stores", fake_get_express_stores)
    monkeypatch.setattr(
        alerts,
        "_get_control_time_courier_shifts",
        fake_get_control_time_courier_shifts,
    )
    monkeypatch.setattr(alerts, "get_admin_telegram_ids", fake_get_admin_telegram_ids)
    monkeypatch.setattr(
        alerts,
        "_get_supervisor_incident_groups",
        fake_get_supervisor_incident_groups,
    )

    bot = _FakeBot()
    await alerts.check_no_online_couriers(bot, "08:15", control_ts=control_ts)

    assert [chat_id for chat_id, _text in bot.calls] == [100]
