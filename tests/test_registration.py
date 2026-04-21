from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.bot.handlers import registration
from app.bot.keyboards.callbacks import AdminApprovalCB, AdminRoleSelectCB
from app.core.admin_user_lookup import phone_lookup_variants
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.bot_user_admin_notification import BotUserAdminNotification


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

    def scalars(self) -> _FakeScalarsResult:
        values = self._value if isinstance(self._value, list) else []
        return _FakeScalarsResult(values)


class _FakeScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class _FakeSession:
    def __init__(self, admin_user: AdminUser | None = None, user: BotUser | None = None) -> None:
        self.admin_user = admin_user
        self.user = user
        self.deleted: list[BotUser] = []
        self.added: list[object] = []
        self.notifications: list[BotUserAdminNotification] = []

    async def execute(self, query: object) -> _FakeExecuteResult:
        entity = getattr(query, "column_descriptions", [{}])[0].get("entity")
        if entity is AdminUser:
            return _FakeExecuteResult(self.admin_user)
        if entity is BotUserAdminNotification:
            return _FakeExecuteResult(self.notifications)
        return _FakeExecuteResult(None)

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, BotUserAdminNotification):
            self.notifications.append(instance)

    async def flush(self) -> None:
        if self.added:
            for instance in self.added:
                if isinstance(instance, BotUser) and instance.id is None:
                    instance.id = 321

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
        self.messages: list[tuple[int, str, object | None]] = []
        self.edits: list[tuple[int, int, str]] = []
        self._message_id = 1000

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: object | None = None,
    ) -> SimpleNamespace:
        self.calls.append(chat_id)
        self.messages.append((chat_id, text, reply_markup))
        self._message_id += 1
        return SimpleNamespace(message_id=self._message_id)

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> None:
        self.edits.append((chat_id, message_id, text))


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


@pytest.mark.parametrize(
    ("phone_digits", "expected"),
    [
        ("79991234567", {"79991234567", "89991234567", "+79991234567"}),
        ("89991234567", {"89991234567", "79991234567", "+79991234567"}),
        ("9991234567", {"9991234567"}),
    ],
)
def test_phone_lookup_variants(phone_digits: str, expected: set[str]) -> None:
    assert phone_lookup_variants(phone_digits) == expected


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
async def test_admin_assign_role_notifies_other_admins(
) -> None:
    callback = _FakeCallback(telegram_id=700)
    user = BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING)
    market_session = _FakeSession(user=user)
    market_session.notifications = [
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=700, message_id=1001),
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=701, message_id=1002),
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=702, message_id=1003),
    ]
    bot = _FakeBot()
    state = _FakeState()
    admin = BotUser(telegram_id=700, name="DB Admin", role=UserRole.ADMIN)

    await registration.admin_assign_role(
        callback,
        AdminRoleSelectCB(user_id=55, role="courier"),
        market_session,
        bot,
        state,
        bot_user=admin,
    )

    assert user.role == UserRole.COURIER
    assert bot.calls == [999]
    assert bot.edits == [
        (701, 1002, "✅ <b>Pending User</b> уже одобрен.\n\nРоль: 🚚 Курьер"),
        (702, 1003, "✅ <b>Pending User</b> уже одобрен.\n\nРоль: 🚚 Курьер"),
    ]


@pytest.mark.asyncio
async def test_admin_can_assign_admin_role() -> None:
    callback = _FakeCallback(telegram_id=700)
    user = BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING)
    market_session = _FakeSession(user=user)
    market_session.notifications = [
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=700, message_id=1001),
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=701, message_id=1002),
    ]
    bot = _FakeBot()
    state = _FakeState()
    admin = BotUser(telegram_id=700, name="DB Admin", role=UserRole.ADMIN)

    await registration.admin_assign_role(
        callback,
        AdminRoleSelectCB(user_id=55, role="admin"),
        market_session,
        bot,
        state,
        bot_user=admin,
    )

    assert user.role == UserRole.ADMIN
    assert "👑 Админ" in callback.message.edits[0][0]
    assert bot.calls == [999]
    assert bot.edits == [
        (701, 1002, "✅ <b>Pending User</b> уже одобрен.\n\nРоль: 👑 Админ"),
    ]


@pytest.mark.asyncio
async def test_admin_save_supervisor_role_persists_store_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = _FakeCallback(telegram_id=700)
    user = BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.PENDING)
    market_session = _FakeSession(user=user)
    market_session.notifications = [
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=700, message_id=1001),
        BotUserAdminNotification(bot_user_id=55, admin_telegram_id=701, message_id=1002),
    ]
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
    assert bot.edits == [
        (
            701,
            1002,
            "✅ <b>Pending User</b> уже одобрен.\n\n"
            "Роль: 📋 Супервайзер\n"
            "Привязанные склады:\n"
            "• Store 10\n"
            "• Store 20",
        ),
    ]
    assert "Привязанные склады" in callback.message.edits[0][0]


@pytest.mark.asyncio
async def test_admin_approve_shows_already_approved_status() -> None:
    callback = _FakeCallback(telegram_id=700)
    market_session = _FakeSession(
        user=BotUser(id=55, telegram_id=999, name="Pending User", role=UserRole.COURIER),
    )
    bot_user = BotUser(telegram_id=700, name="DB Admin", role=UserRole.ADMIN)

    await registration.admin_approve(
        callback,
        AdminApprovalCB(user_id=55, action="approve"),
        market_session,
        bot_user=bot_user,
    )

    assert callback.answers == [None]
    assert "уже одобрен" in callback.message.edits[0][0]


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
    added_users = [item for item in market_session.added if isinstance(item, BotUser)]
    added_notifications = [
        item for item in market_session.added if isinstance(item, BotUserAdminNotification)
    ]
    assert [user.role for user in added_users] == [UserRole.PENDING]
    assert bot.calls == [101, 202, 303]
    assert [(item.admin_telegram_id, item.message_id) for item in added_notifications] == [
        (101, 1001),
        (202, 1002),
        (303, 1003),
    ]
