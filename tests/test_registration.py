from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.bot.handlers import registration
from app.bot.keyboards.callbacks import AdminApprovalCB, AdminRoleSelectCB
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import BotUser, UserRole


class _FakeState:
    def __init__(self) -> None:
        self.cleared = False
        self.current_state: object | None = None
        self.data: dict[str, object] = {}

    async def clear(self) -> None:
        self.cleared = True
        self.current_state = None
        self.data = {}

    async def set_state(self, state: object) -> None:
        self.current_state = state

    async def update_data(self, **kwargs: object) -> dict[str, object]:
        self.data.update(kwargs)
        return self.data

    async def get_data(self) -> dict[str, object]:
        return self.data


class _FakeExecuteResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _FakeSession:
    def __init__(self, admin_user: AdminUser | None = None, user: BotUser | None = None) -> None:
        self.admin_user = admin_user
        self.user = user
        self.deleted: list[BotUser] = []
        self.added: list[BotUser] = []

    async def execute(self, _query: object) -> _FakeExecuteResult:
        return _FakeExecuteResult(self.admin_user)

    def add(self, user: BotUser) -> None:
        self.added.append(user)

    async def flush(self) -> None:
        if self.added:
            self.added[-1].id = 321

    async def get(self, _model: object, _user_id: int) -> BotUser | None:
        return self.user

    async def delete(self, user: BotUser) -> None:
        self.deleted.append(user)


class _FakeMessage:
    def __init__(self) -> None:
        self.answers: list[tuple[str, object | None]] = []
        self.edits: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append((text, reply_markup))

    async def edit_text(self, text: str, reply_markup: object | None = None) -> None:
        self.edits.append((text, reply_markup))


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: object | None = None,
    ) -> None:
        self.calls.append(chat_id)


class _FakeCallback:
    def __init__(self, telegram_id: int) -> None:
        self.from_user = SimpleNamespace(id=telegram_id)
        self.message = _FakeMessage()
        self.answers: list[str | None] = []

    async def answer(self, text: str | None = None) -> None:
        self.answers.append(text)


class _FakeContactMessage(_FakeMessage):
    def __init__(self) -> None:
        super().__init__()
        self.contact = SimpleNamespace(user_id=500, phone_number="+79991234567")
        self.from_user = SimpleNamespace(id=500, username="new_user")


@pytest.mark.asyncio
async def test_admin_approve_allows_db_admin() -> None:
    callback = _FakeCallback(telegram_id=700)
    market_session = _FakeSession(
        user=BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING),
    )
    bot_user = BotUser(telegram_id=700, name="DB Admin", role=UserRole.ADMIN)

    await registration.admin_approve(
        callback,
        AdminApprovalCB(user_id=55, action="approve"),
        market_session,
        bot_user=bot_user,
    )

    assert callback.answers == [None]
    assert callback.message.edits
    assert "Выберите роль" in callback.message.edits[0][0]


@pytest.mark.asyncio
async def test_admin_reject_allows_fallback_admin(
) -> None:
    callback = _FakeCallback(telegram_id=1917662916)
    user = BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING)
    market_session = _FakeSession(user=user)
    bot = _FakeBot()

    await registration.admin_reject(
        callback,
        AdminApprovalCB(user_id=55, action="reject"),
        market_session,
        bot,
    )

    assert market_session.deleted == [user]
    assert bot.calls == [999]


@pytest.mark.asyncio
async def test_admin_assign_role_blocks_non_admin() -> None:
    callback = _FakeCallback(telegram_id=800)
    market_session = _FakeSession(
        user=BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING),
    )
    bot = _FakeBot()
    state = _FakeState()
    supervisor = BotUser(telegram_id=800, name="Supervisor", role=UserRole.SUPERVISOR)

    await registration.admin_assign_role(
        callback,
        AdminRoleSelectCB(user_id=55, role="courier"),
        market_session,
        bot,
        state,
        bot_user=supervisor,
    )

    assert callback.answers == ["⛔️ Только администратор."]
    assert callback.message.edits == []
    assert bot.calls == []


@pytest.mark.asyncio
async def test_admin_save_supervisor_role_persists_store_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = _FakeCallback(telegram_id=700)
    user = BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING)
    market_session = _FakeSession(user=user)
    bot = _FakeBot()
    state = _FakeState()
    admin = BotUser(telegram_id=700, name="DB Admin", role=UserRole.ADMIN)

    await state.set_state(registration.RegistrationForm.supervisor_stores)
    await state.update_data(supervisor_user_id=55, supervisor_store_ids=[10, 20])

    async def fake_get_accessible_stores(_session: object) -> list[object]:
        return [
            SimpleNamespace(id=10, display_name="Store 10"),
            SimpleNamespace(id=20, display_name="Store 20"),
        ]

    monkeypatch.setattr(registration, "get_accessible_stores", fake_get_accessible_stores)

    await registration.admin_save_supervisor_role(
        callback,
        registration.AdminSupervisorStoreActionCB(user_id=55, action="save"),
        market_session,
        bot,
        state,
        bot_user=admin,
    )

    assert user.role == UserRole.SUPERVISOR
    assert user.assigned_store_ids == [10, 20]
    assert state.cleared is True
    assert bot.calls == [999]
    assert "Привязанные склады" in callback.message.edits[0][0]


@pytest.mark.asyncio
async def test_reg_contact_notifies_all_admins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_admin_telegram_ids(_session: object) -> list[int]:
        return [101, 202, 303]

    monkeypatch.setattr(registration, "get_admin_telegram_ids", fake_get_admin_telegram_ids)

    admin_user = AdminUser(
        id=1,
        name="Ivan",
        surname="Petrov",
        email="ivan@example.com",
        phone="+79991234567",
    )
    market_session = _FakeSession(admin_user=admin_user)
    message = _FakeContactMessage()
    state = _FakeState()
    bot = _FakeBot()

    await registration.reg_contact(
        message,
        state,
        market_session,
        bot,
    )

    assert state.cleared is True
    assert [user.role for user in market_session.added] == [UserRole.PENDING]
    assert bot.calls == [101, 202, 303]
