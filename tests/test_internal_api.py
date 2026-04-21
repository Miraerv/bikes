# ruff: noqa: S101

from __future__ import annotations

import pytest

from app import internal_api


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
        self.calls: list[int] = []
        self.messages: list[str] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.calls.append(chat_id)
        self.messages.append(text)
        if chat_id == 100:
            raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("layer", "minutes", "expected"),
    [
        (1, 45, True),
        (1, 46, False),
        (2, 60, True),
        (2, 61, False),
        (0, 0, False),
    ],
)
def test_is_order_within_sla(layer: int, minutes: int, expected: bool) -> None:
    assert internal_api._is_order_within_sla(layer, minutes) is expected


@pytest.mark.asyncio
async def test_handle_shift_ended_notifies_all_admins_even_if_one_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_shift_stats(
        _shift_id: int,
        _admin_user_id: int,
    ) -> internal_api.ShiftStats:
        return internal_api.ShiftStats(courier_name="Courier Name", total_orders=5, sla=95.0)

    async def fake_get_admin_telegram_ids(_session: object) -> list[int]:
        return [100, 200, 300]

    monkeypatch.setattr(internal_api, "_get_shift_stats", fake_get_shift_stats)
    monkeypatch.setattr(internal_api, "get_admin_telegram_ids", fake_get_admin_telegram_ids)
    monkeypatch.setattr(internal_api, "market_session_maker", lambda: _FakeSession())

    bot = _FakeBot()
    await internal_api._handle_shift_ended(
        bot,
        {"admin_user_id": 1, "shift_id": 42},
    )

    assert bot.calls == [100, 200, 300]
