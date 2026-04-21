from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.core.breakdown_flow import BreakdownDraft, create_breakdown
from app.core.display import (
    MISSING_LABEL,
    bike_label,
    display_name_label,
    optional_minutes_label,
    optional_money_label,
    optional_text_label,
)
from app.core.registration_flow import (
    admin_user_registration_name,
    assign_role,
    assign_supervisor_role,
)
from app.core.repair_flow import (
    RepairPickupConfirmation,
    RepairPickupDraft,
    format_pickup_breakdown_label,
    parse_repair_cost,
    parse_repair_duration,
)
from app.core.usage_flow import (
    TakeBikeDraft,
    UsageShiftSummary,
    create_usage_log,
    format_active_shift_lines,
)
from app.db.models.admin_user import AdminUser
from app.db.models.bike import Bike
from app.db.models.bike_breakdown import BreakdownType
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.store import Store


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("-", None),
        ("15", 15),
        (" 45 ", 45),
    ],
)
def test_parse_repair_duration(raw_text: str, expected: int | None) -> None:
    assert parse_repair_duration(raw_text) == expected


@pytest.mark.parametrize(
    ("raw_text", "error"),
    [
        ("0", "duration_must_be_positive"),
        ("oops", "duration_must_be_integer"),
    ],
)
def test_parse_repair_duration_errors(raw_text: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        parse_repair_duration(raw_text)


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("-", None),
        ("1200", Decimal("1200")),
        ("1200,50", Decimal("1200.50")),
    ],
)
def test_parse_repair_cost(raw_text: str, expected: Decimal | None) -> None:
    assert parse_repair_cost(raw_text) == expected


def test_display_labels_handle_missing_values() -> None:
    bike = Bike(bike_number="B-1", model="Model X", commissioned_at=datetime(2026, 4, 21))
    store = Store(title="Store title", street="Store street")

    assert bike_label(bike) == "B-1 — Model X"
    assert bike_label(None) == MISSING_LABEL
    assert display_name_label(store) == "Store street"
    assert display_name_label(None) == MISSING_LABEL
    assert optional_text_label("Text") == "Text"
    assert optional_text_label(None) == MISSING_LABEL
    assert optional_minutes_label(30) == "30 мин."
    assert optional_minutes_label(None) == MISSING_LABEL
    assert optional_money_label(Decimal("10.50")) == "10.50 ₽"
    assert optional_money_label(None) == MISSING_LABEL


def test_format_pickup_breakdown_label_uses_intermediate_result() -> None:
    confirmation = RepairPickupConfirmation(
        draft=RepairPickupDraft(
            bike_id=1,
            store_id=2,
            breakdown_id=3,
            mechanic_id=4,
            mechanic_name="Mechanic",
        ),
        bike_label="Bike",
        store_label="Store",
        mechanic_name="Mechanic",
        breakdown_type="brakes",
        breakdown_reported_at=datetime(2026, 4, 21, 10, 0),
    )

    assert format_pickup_breakdown_label(
        confirmation,
        {"brakes": "Тормоза"},
        {"brakes": "B"},
    ) == "B Тормоза (21.04.2026)"


def test_create_usage_log_from_draft() -> None:
    started_at = datetime(2026, 4, 21, 9, 30)
    log = create_usage_log(
        TakeBikeDraft(bike_id=10, courier_id=20, store_id=30),
        started_at=started_at,
    )

    assert log.bike_id == 10
    assert log.courier_id == 20
    assert log.store_id == 30
    assert log.started_at == started_at


def test_format_active_shift_lines() -> None:
    lines = format_active_shift_lines([
        UsageShiftSummary(
            log_id=1,
            bike_number="B-1",
            bike_model="Model",
            courier_name="Courier",
            store_name="Store",
            started_at=datetime(2026, 4, 21, 9, 30),
        ),
    ])

    assert lines[0] == "👀 <b>Активные смены</b>"
    assert "B-1" in lines[3]
    assert "Courier" in lines[3]


def test_create_breakdown_from_draft() -> None:
    breakdown = create_breakdown(
        BreakdownDraft(
            bike_id=10,
            store_id=20,
            breakdown_type="brakes",
            description="Скрипят тормоза",
            photo_ids=("file-1",),
            courier_id=30,
            courier_name="Courier",
        ),
        reported_at=datetime(2026, 4, 21, 9, 30),
    )

    assert breakdown.bike_id == 10
    assert breakdown.courier_id == 30
    assert breakdown.reported_by == 30
    assert breakdown.breakdown_type == BreakdownType.BRAKES


def test_registration_name_and_role_assignment() -> None:
    admin_user = AdminUser(
        id=1,
        name="Ivan",
        surname="Petrov",
        email="ivan@example.com",
        phone="+79991234567",
    )
    bot_user = BotUser(
        telegram_id=500,
        name="Ivan Petrov",
        role=UserRole.PENDING,
        store_ids="[10]",
    )

    assert admin_user_registration_name(admin_user) == "Ivan Petrov"
    assert assign_role(bot_user, UserRole.MECHANIC) == "🔧 Мастер"
    assert bot_user.role == UserRole.MECHANIC
    assert bot_user.store_ids is None

    assert assign_supervisor_role(bot_user, [20, 10]) == "📋 Супервайзер"
    assert bot_user.role == UserRole.SUPERVISOR
    assert bot_user.assigned_store_ids == [10, 20]
