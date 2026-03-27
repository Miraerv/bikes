"""Inline keyboard builders for bike CRUD flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    AddBikeConfirmCB,
    AnalyticsMenuCB,
    BikeCardCB,
    BikeDecommissionCB,
    BikeListCB,
    BikeMenuCB,
    BikeStatusCB,
    BreakdownBikeSelectCB,
    BreakdownConfirmCB,
    BreakdownCourierSelectCB,
    BreakdownHistoryCB,
    BreakdownMenuCB,
    BreakdownSkipPhotoCB,
    BreakdownTypeCB,
    DashboardMenuCB,
    DashboardStoreCB,
    RepairBikeSelectCB,
    RepairBreakdownSelectCB,
    RepairBreakdownSkipCB,
    RepairCompleteConfirmCB,
    RepairMechanicSelectCB,
    RepairMenuCB,
    RepairPickupConfirmCB,
    RepairSelectCB,
    StatusFilterCB,
    StoreSelectCB,
    UsageBikeSelectCB,
    UsageConfirmCB,
    UsageCourierSelectCB,
    UsageMenuCB,
    UsageReturnBikeCB,
    UsageReturnConfirmCB,
)
from app.db.models.bike import BikeStatus

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.admin_user import AdminUser
    from app.db.models.bike import Bike
    from app.db.models.bike_breakdown import BikeBreakdown
    from app.db.models.bike_repair import BikeRepair
    from app.db.models.bike_usage_log import BikeUsageLog
    from app.db.models.store import Store

# ── Status display helpers ──────────────────────────────────────────────

STATUS_EMOJI: dict[str, str] = {
    "online": "🟢",
    "inspection": "🟡",
    "repair": "🔴",
    "decommissioned": "⚫",
}

STATUS_LABEL: dict[str, str] = {
    "online": "На линии",
    "inspection": "Проверка",
    "repair": "Ремонт",
    "decommissioned": "Списан",
}

ITEMS_PER_PAGE = 5


# ── Main bike menu ─────────────────────────────────────────────────────


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu shown after /start."""
    b = InlineKeyboardBuilder()
    b.button(text="🚲 Байки", callback_data=BikeMenuCB(action="open"))
    b.button(text="📊 Смены", callback_data=UsageMenuCB(action="open"))
    b.button(text="🔧 Поломки", callback_data=BreakdownMenuCB(action="open"))
    b.button(text="🛠 Ремонт", callback_data=RepairMenuCB(action="open"))
    b.button(text="📈 Парк байков", callback_data=DashboardMenuCB(action="open"))
    b.button(text="📊 Аналитика", callback_data=AnalyticsMenuCB(action="open"))
    b.adjust(2, 2, 2)
    return b.as_markup()


def bike_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: list bikes / add bike."""
    b = InlineKeyboardBuilder()
    b.button(text="📋 Список байков", callback_data=BikeMenuCB(action="list"))
    b.button(text="➕ Добавить байк", callback_data=BikeMenuCB(action="add"))
    b.button(text="← Назад", callback_data=BikeMenuCB(action="back"))
    b.adjust(2, 1)
    return b.as_markup()


# ── Store selection ─────────────────────────────────────────────────────


def store_select_kb(stores: list[Store], purpose: str) -> InlineKeyboardMarkup:
    """Grid of stores for selection.  purpose = 'filter' | 'add'."""
    b = InlineKeyboardBuilder()
    if purpose == "filter":
        b.button(
            text="📦 Все склады",
            callback_data=StoreSelectCB(store_id=0, purpose=purpose),
        )
    for store in stores:
        b.button(
            text=f"🏪 {store.display_name}",
            callback_data=StoreSelectCB(store_id=store.id, purpose=purpose),
        )
    b.adjust(2)
    return b.as_markup()


# ── Status filter ───────────────────────────────────────────────────────


def status_filter_kb(store_id: int) -> InlineKeyboardMarkup:
    """Filter by status before showing the list."""
    b = InlineKeyboardBuilder()
    b.button(text="📊 Все", callback_data=StatusFilterCB(store_id=store_id, status="all"))
    for status in BikeStatus:
        emoji = STATUS_EMOJI[status.value]
        label = STATUS_LABEL[status.value]
        b.button(
            text=f"{emoji} {label}",
            callback_data=StatusFilterCB(store_id=store_id, status=status.value),
        )
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(3, 2, 1)
    return b.as_markup()


# ── Paginated bike list ─────────────────────────────────────────────────


def bike_list_kb(
    bikes: list[Bike],
    page: int,
    total: int,
    store_id: int,
    status: str,
) -> InlineKeyboardMarkup:
    """Paginated list of bikes."""
    b = InlineKeyboardBuilder()

    # Bike buttons
    for bike in bikes:
        emoji = STATUS_EMOJI.get(bike.status.value, "❓")
        b.button(
            text=f"{emoji} {bike.bike_number} — {bike.model}",
            callback_data=BikeCardCB(bike_id=bike.id),
        )

    # Navigation row
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    nav_buttons: list[tuple[str, BikeListCB]] = []

    if page > 0:
        nav_buttons.append((
            "◀️",
            BikeListCB(store_id=store_id, status=status, page=page - 1),
        ))

    nav_buttons.append((
        f"📄 {page + 1}/{total_pages}",
        BikeListCB(store_id=store_id, status=status, page=page),
    ))

    if (page + 1) < total_pages:
        nav_buttons.append((
            "▶️",
            BikeListCB(store_id=store_id, status=status, page=page + 1),
        ))

    for text, cb in nav_buttons:
        b.button(text=text, callback_data=cb)

    # Back button
    b.button(text="← Назад", callback_data=BikeMenuCB(action="open"))

    # Layout: each bike on its own row, then nav row, then back
    bike_rows = [1] * len(bikes)
    b.adjust(*bike_rows, len(nav_buttons), 1)

    return b.as_markup()


# ── Bike card actions ───────────────────────────────────────────────────


def bike_card_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Action buttons on a bike card."""
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Изменить статус", callback_data=BikeStatusCB(bike_id=bike_id, status="pick"))
    b.button(
        text="⚫ Списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=False),
    )
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(2, 1)
    return b.as_markup()


# ── Status change ───────────────────────────────────────────────────────


def bike_status_select_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Choose new status for a bike."""
    b = InlineKeyboardBuilder()
    for status in BikeStatus:
        emoji = STATUS_EMOJI[status.value]
        label = STATUS_LABEL[status.value]
        b.button(
            text=f"{emoji} {label}",
            callback_data=BikeStatusCB(bike_id=bike_id, status=status.value),
        )
    b.button(text="← Отмена", callback_data=BikeCardCB(bike_id=bike_id))
    b.adjust(2, 2, 1)
    return b.as_markup()


# ── Decommission confirm ───────────────────────────────────────────────


def confirm_decommission_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Yes / No confirmation for decommissioning."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=True),
    )
    b.button(text="❌ Отмена", callback_data=BikeCardCB(bike_id=bike_id))
    b.adjust(2)
    return b.as_markup()


# ── Add bike confirm ───────────────────────────────────────────────────


def add_bike_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm / cancel adding a new bike."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сохранить", callback_data=AddBikeConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=AddBikeConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


# ── Usage log keyboards (Stage 3) ──────────────────────────────────────


def usage_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: take bike / return bike / active shifts."""
    b = InlineKeyboardBuilder()
    b.button(text="🚴 Взял байк", callback_data=UsageMenuCB(action="take"))
    b.button(text="🔙 Вернул байк", callback_data=UsageMenuCB(action="return"))
    b.button(text="👀 Кто на байке", callback_data=UsageMenuCB(action="active"))
    b.button(text="← Назад", callback_data=UsageMenuCB(action="back"))
    b.adjust(2, 1, 1)
    return b.as_markup()


def usage_bike_select_kb(bikes: list[Bike], store_id: int) -> InlineKeyboardMarkup:
    """List of available (online) bikes for taking."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        b.button(
            text=f"🚲 {bike.bike_number} — {bike.model}",
            callback_data=UsageBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_courier_select_kb(
    couriers: list[AdminUser], bike_id: int, store_id: int,
) -> InlineKeyboardMarkup:
    """List of couriers to assign to the shift."""
    b = InlineKeyboardBuilder()
    for courier in couriers:
        b.button(
            text=f"👤 {courier.display_name}",
            callback_data=UsageCourierSelectCB(
                courier_id=courier.id, bike_id=bike_id, store_id=store_id,
            ),
        )
    b.button(text="← Отмена", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(couriers) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_confirm_take_kb() -> InlineKeyboardMarkup:
    """Confirm / cancel taking a bike."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=UsageConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=UsageConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def usage_active_logs_kb(logs: list[BikeUsageLog]) -> InlineKeyboardMarkup:
    """List of active shifts with return buttons."""
    b = InlineKeyboardBuilder()
    for log in logs:
        courier_name = log.courier.display_name if log.courier else "—"
        bike_num = log.bike.bike_number if log.bike else "—"
        started = log.started_at.strftime("%H:%M")
        b.button(
            text=f"🔙 {bike_num} • {courier_name} ({started})",
            callback_data=UsageReturnBikeCB(log_id=log.id),
        )
    b.button(text="← Назад", callback_data=UsageMenuCB(action="open"))
    rows = [1] * len(logs) + [1]
    b.adjust(*rows)
    return b.as_markup()


def usage_return_confirm_kb(log_id: int) -> InlineKeyboardMarkup:
    """Confirm returning a bike."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, вернул",
        callback_data=UsageReturnConfirmCB(log_id=log_id, confirm=True),
    )
    b.button(
        text="❌ Отмена",
        callback_data=UsageReturnConfirmCB(log_id=log_id, confirm=False),
    )
    b.adjust(2)
    return b.as_markup()


# ── Breakdown keyboards (Stage 4) ─────────────────────────────────────

BREAKDOWN_TYPE_EMOJI: dict[str, str] = {
    "brakes": "🛑",
    "wheel": "🛞",
    "battery": "🔋",
    "motor": "⚙️",
    "frame": "🪨",
    "electronics": "💡",
    "other": "❓",
}

BREAKDOWN_TYPE_LABEL: dict[str, str] = {
    "brakes": "Тормоза",
    "wheel": "Колесо",
    "battery": "Аккумулятор",
    "motor": "Двигатель",
    "frame": "Рама",
    "electronics": "Электроника",
    "other": "Другое",
}


def breakdown_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: create breakdown / back."""
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Создать поломку", callback_data=BreakdownMenuCB(action="create"))
    b.button(text="← Назад", callback_data=BreakdownMenuCB(action="back"))
    b.adjust(1)
    return b.as_markup()


def breakdown_bike_select_kb(
    bikes: list[Bike], store_id: int,
) -> InlineKeyboardMarkup:
    """List of bikes at the store (exclude decommissioned)."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        emoji = STATUS_EMOJI.get(bike.status.value, "❓")
        b.button(
            text=f"{emoji} {bike.bike_number} — {bike.model}",
            callback_data=BreakdownBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_type_kb() -> InlineKeyboardMarkup:
    """Choose breakdown type."""
    from app.db.models.bike_breakdown import BreakdownType

    b = InlineKeyboardBuilder()
    for bd_type in BreakdownType:
        emoji = BREAKDOWN_TYPE_EMOJI.get(bd_type.value, "❓")
        label = BREAKDOWN_TYPE_LABEL.get(bd_type.value, bd_type.value)
        b.button(
            text=f"{emoji} {label}",
            callback_data=BreakdownTypeCB(bd_type=bd_type.value),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def breakdown_photo_kb() -> InlineKeyboardMarkup:
    """Photo upload: skip or finish."""
    b = InlineKeyboardBuilder()
    b.button(text="⏭ Пропустить", callback_data=BreakdownSkipPhotoCB(action="skip"))
    b.button(text="✅ Готово", callback_data=BreakdownSkipPhotoCB(action="done"))
    b.adjust(2)
    return b.as_markup()


def breakdown_courier_select_kb(
    couriers: list[AdminUser],
) -> InlineKeyboardMarkup:
    """List of couriers for manual selection during breakdown creation."""
    b = InlineKeyboardBuilder()
    for courier in couriers:
        b.button(
            text=f"👤 {courier.display_name}",
            callback_data=BreakdownCourierSelectCB(courier_id=courier.id),
        )
    b.button(text="← Отмена", callback_data=BreakdownMenuCB(action="open"))
    rows = [1] * len(couriers) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel breakdown creation."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сохранить", callback_data=BreakdownConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=BreakdownConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def breakdown_history_kb(
    breakdowns: list[BikeBreakdown],
    bike_id: int,
) -> InlineKeyboardMarkup:
    """List breakdowns for a bike card — each is clickable for detail."""
    from app.bot.keyboards.callbacks import BreakdownDetailCB

    b = InlineKeyboardBuilder()
    for bd in breakdowns:
        bd_emoji = BREAKDOWN_TYPE_EMOJI.get(bd.breakdown_type.value, "❓")
        bd_label = BREAKDOWN_TYPE_LABEL.get(bd.breakdown_type.value, bd.breakdown_type.value)
        reported = bd.reported_at.strftime("%d.%m") if bd.reported_at else "—"
        photo_icon = "📷" if bd.photos else ""
        b.button(
            text=f"{bd_emoji} {bd_label} ({reported}) {photo_icon}",
            callback_data=BreakdownDetailCB(breakdown_id=bd.id, bike_id=bike_id),
        )
    b.button(text="← Назад", callback_data=BikeCardCB(bike_id=bike_id))
    rows = [1] * len(breakdowns) + [1]
    b.adjust(*rows)
    return b.as_markup()


def breakdown_detail_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Back button from breakdown detail to breakdown list."""
    b = InlineKeyboardBuilder()
    b.button(text="← К списку поломок", callback_data=BreakdownHistoryCB(bike_id=bike_id))
    b.adjust(1)
    return b.as_markup()


def bike_card_actions_kb(bike_id: int) -> InlineKeyboardMarkup:
    """Action buttons on a bike card — with breakdown history link."""
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Изменить статус", callback_data=BikeStatusCB(bike_id=bike_id, status="pick"))
    b.button(
        text="⚫ Списать",
        callback_data=BikeDecommissionCB(bike_id=bike_id, confirm=False),
    )
    b.button(text="📋 Поломки", callback_data=BreakdownHistoryCB(bike_id=bike_id))
    b.button(text="← Назад", callback_data=BikeMenuCB(action="list"))
    b.adjust(2, 1, 1)
    return b.as_markup()


# ── Repair keyboards (Stage 5) ────────────────────────────────────────


def repair_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: pickup bike / complete / my repairs / back."""
    b = InlineKeyboardBuilder()
    b.button(text="📥 Забрал байк", callback_data=RepairMenuCB(action="pickup"))
    b.button(text="✅ Байк готов", callback_data=RepairMenuCB(action="complete"))
    b.button(text="📋 Мои ремонты", callback_data=RepairMenuCB(action="my_repairs"))
    b.button(text="← Назад", callback_data=RepairMenuCB(action="back"))
    b.adjust(2, 1, 1)
    return b.as_markup()


def repair_bike_select_kb(
    bikes: list[Bike], store_id: int,
) -> InlineKeyboardMarkup:
    """List of bikes available for repair pickup (inspection/repair status)."""
    b = InlineKeyboardBuilder()
    for bike in bikes:
        emoji = STATUS_EMOJI.get(bike.status.value, "❓")
        b.button(
            text=f"{emoji} {bike.bike_number} — {bike.model}",
            callback_data=RepairBikeSelectCB(bike_id=bike.id, store_id=store_id),
        )
    b.button(text="← Отмена", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(bikes) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_breakdown_select_kb(
    breakdowns: list[BikeBreakdown],
) -> InlineKeyboardMarkup:
    """List of open breakdowns for linking to a repair + skip button."""
    b = InlineKeyboardBuilder()
    for bd in breakdowns:
        bd_emoji = BREAKDOWN_TYPE_EMOJI.get(bd.breakdown_type.value, "❓")
        bd_label = BREAKDOWN_TYPE_LABEL.get(bd.breakdown_type.value, bd.breakdown_type.value)
        reported = bd.reported_at.strftime("%d.%m")
        b.button(
            text=f"{bd_emoji} {bd_label} ({reported})",
            callback_data=RepairBreakdownSelectCB(breakdown_id=bd.id),
        )
    b.button(text="⏭ Без привязки", callback_data=RepairBreakdownSkipCB(action="skip"))
    rows = [1] * len(breakdowns) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_mechanic_select_kb(
    mechanics: list[AdminUser],
) -> InlineKeyboardMarkup:
    """List of mechanics for selection."""
    b = InlineKeyboardBuilder()
    for mech in mechanics:
        b.button(
            text=f"🔧 {mech.display_name}",
            callback_data=RepairMechanicSelectCB(mechanic_id=mech.id),
        )
    b.button(text="← Отмена", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(mechanics) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_pickup_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel repair pickup."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=RepairPickupConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=RepairPickupConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def repair_active_list_kb(repairs: list[BikeRepair]) -> InlineKeyboardMarkup:
    """List of active (in-progress) repairs for completion."""
    b = InlineKeyboardBuilder()
    for repair in repairs:
        bike_num = repair.bike.bike_number if repair.bike else "—"
        picked = repair.picked_up_at.strftime("%d.%m %H:%M")
        b.button(
            text=f"🔴 {bike_num} (с {picked})",
            callback_data=RepairSelectCB(repair_id=repair.id),
        )
    b.button(text="← Назад", callback_data=RepairMenuCB(action="open"))
    rows = [1] * len(repairs) + [1]
    b.adjust(*rows)
    return b.as_markup()


def repair_complete_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm or cancel repair completion."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Завершить", callback_data=RepairCompleteConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=RepairCompleteConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()


def repair_my_list_kb(
    repairs: list[BikeRepair],  # noqa: ARG001
) -> InlineKeyboardMarkup:
    """List of all repairs for a mechanic (current + completed)."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад", callback_data=RepairMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()


# ── Dashboard keyboards (Stage 6) ─────────────────────────────────────


def dashboard_stores_kb(
    stores: list[tuple[Store, dict[str, int]]],
) -> InlineKeyboardMarkup:
    """List of stores with bike counts for dashboard drill-down."""
    b = InlineKeyboardBuilder()
    for store, counts in stores:
        total = sum(counts.values())
        online = counts.get("online", 0)
        repair = counts.get("repair", 0) + counts.get("inspection", 0)
        b.button(
            text=f"🏪 {store.display_name}  ({online}✅ / {repair}🔧 / {total})",
            callback_data=DashboardStoreCB(store_id=store.id),
        )
    b.button(text="← Назад", callback_data=DashboardMenuCB(action="back"))
    rows = [1] * len(stores) + [1]
    b.adjust(*rows)
    return b.as_markup()


def dashboard_back_kb() -> InlineKeyboardMarkup:
    """Back button from store detail to dashboard."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад к дашборду", callback_data=DashboardMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()


# ── Analytics keyboards (Stage 7) ──────────────────────────────────────


def analytics_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: analytics reports."""
    b = InlineKeyboardBuilder()
    b.button(
        text="📋 Поломки за месяц",
        callback_data=AnalyticsMenuCB(action="breakdowns_month"),
    )
    b.button(
        text="👤 Поломки по курьерам",
        callback_data=AnalyticsMenuCB(action="breakdowns_couriers"),
    )
    b.button(
        text="🔴 Ненадёжные байки",
        callback_data=AnalyticsMenuCB(action="unreliable_bikes"),
    )
    b.button(
        text="🛠 Ремонты",
        callback_data=AnalyticsMenuCB(action="bike_repairs"),
    )
    b.button(
        text="⏱ Даунтайм",
        callback_data=AnalyticsMenuCB(action="downtime"),
    )
    b.button(
        text="✅ Аккуратные курьеры",
        callback_data=AnalyticsMenuCB(action="careful_couriers"),
    )
    b.button(text="← Назад", callback_data=AnalyticsMenuCB(action="back"))
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def analytics_back_kb() -> InlineKeyboardMarkup:
    """Back button from report to analytics menu."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад к аналитике", callback_data=AnalyticsMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()


# ── Courier keyboards (Stage 11) ──────────────────────────────────────


def courier_menu_kb() -> InlineKeyboardMarkup:
    """Courier main menu: take / return bike."""
    from app.bot.keyboards.callbacks import CourierMenuCB

    b = InlineKeyboardBuilder()
    b.button(text="🚴 Взял байк", callback_data=CourierMenuCB(action="take"))
    b.button(text="🔙 Вернул байк", callback_data=CourierMenuCB(action="return"))
    b.adjust(1)
    return b.as_markup()


def courier_take_confirm_kb() -> InlineKeyboardMarkup:
    """Confirm / cancel taking a bike (courier)."""
    from app.bot.keyboards.callbacks import CourierTakeConfirmCB

    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=CourierTakeConfirmCB(action="save"))
    b.button(text="❌ Отмена", callback_data=CourierTakeConfirmCB(action="cancel"))
    b.adjust(2)
    return b.as_markup()
