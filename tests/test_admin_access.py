from __future__ import annotations

import pytest

from app.core.admin_access import get_admin_telegram_ids, is_admin_actor
from app.core.config import settings
from app.db.models.bot_user import BotUser, UserRole


class _FakeResult:
    def __init__(self, rows: list[tuple[int]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[int]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[tuple[int]]) -> None:
        self._rows = rows

    async def execute(self, _query: object) -> _FakeResult:
        return _FakeResult(self._rows)


@pytest.mark.parametrize(
    ("bot_user", "telegram_id", "expected"),
    [
        (None, 1917662916, True),
        (BotUser(telegram_id=10, name="Admin", role=UserRole.ADMIN), 10, True),
        (BotUser(telegram_id=11, name="Sup", role=UserRole.SUPERVISOR), 11, False),
        (BotUser(telegram_id=12, name="Mech", role=UserRole.MECHANIC), 12, False),
        (BotUser(telegram_id=13, name="Courier", role=UserRole.COURIER), 13, False),
        (BotUser(telegram_id=14, name="Pending", role=UserRole.PENDING), 14, False),
    ],
)
def test_is_admin_actor(
    monkeypatch: pytest.MonkeyPatch,
    bot_user: BotUser | None,
    telegram_id: int,
    expected: bool,
) -> None:
    monkeypatch.setattr(settings, "admin_telegram_id", 1917662916)
    assert is_admin_actor(bot_user, telegram_id) is expected


@pytest.mark.asyncio
async def test_get_admin_telegram_ids_deduplicates_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "admin_telegram_id", 1917662916)
    session = _FakeSession(rows=[(555,), (1917662916,), (777,), (555,)])

    assert await get_admin_telegram_ids(session) == [555, 1917662916, 777]
