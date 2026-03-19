"""Typed CallbackData factories for bike CRUD inline keyboards."""

from aiogram.filters.callback_data import CallbackData


class BikeMenuCB(CallbackData, prefix="bike_menu"):
    """Navigation within the bikes sub-menu."""

    action: str  # list | add | back


class StoreSelectCB(CallbackData, prefix="store_sel"):
    """Store selection (for filtering or adding)."""

    store_id: int  # 0 = all stores
    purpose: str  # filter | add


class StatusFilterCB(CallbackData, prefix="status_f"):
    """Status filter for bike list."""

    store_id: int
    status: str  # all | online | inspection | repair | decommissioned


class BikeListCB(CallbackData, prefix="bike_ls"):
    """Paginated bike list."""

    store_id: int
    status: str
    page: int


class BikeCardCB(CallbackData, prefix="bike_cd"):
    """Open bike card."""

    bike_id: int


class BikeStatusCB(CallbackData, prefix="bike_st"):
    """Change bike status."""

    bike_id: int
    status: str


class BikeDecommissionCB(CallbackData, prefix="bike_dc"):
    """Decommission confirmation."""

    bike_id: int
    confirm: bool


class AddBikeConfirmCB(CallbackData, prefix="add_bike"):
    """Confirm or cancel adding a bike."""

    action: str  # save | cancel


# ── Usage log (Stage 3) ────────────────────────────────────────────────


class UsageMenuCB(CallbackData, prefix="usage_menu"):
    """Navigation within the shifts sub-menu."""

    action: str  # take | return | active | back


class UsageBikeSelectCB(CallbackData, prefix="usage_bike"):
    """Select a bike for taking on shift."""

    bike_id: int
    store_id: int


class UsageCourierSelectCB(CallbackData, prefix="usage_cr"):
    """Select a courier for the shift."""

    courier_id: int
    bike_id: int
    store_id: int


class UsageConfirmCB(CallbackData, prefix="usage_cf"):
    """Confirm or cancel taking a bike."""

    action: str  # save | cancel


class UsageReturnBikeCB(CallbackData, prefix="usage_ret"):
    """Select an active shift to return bike."""

    log_id: int


class UsageReturnConfirmCB(CallbackData, prefix="usage_rc"):
    """Confirm returning a bike."""

    log_id: int
    confirm: bool


class UsageActiveStoreCB(CallbackData, prefix="usage_as"):
    """Select store to view active shifts."""

    store_id: int  # 0 = all stores


# ── Breakdown (Stage 4) ────────────────────────────────────────────────


class BreakdownMenuCB(CallbackData, prefix="bd_menu"):
    """Navigation within the breakdowns sub-menu."""

    action: str  # open | back


class BreakdownBikeSelectCB(CallbackData, prefix="bd_bike"):
    """Select a bike when creating a breakdown."""

    bike_id: int
    store_id: int


class BreakdownTypeCB(CallbackData, prefix="bd_type"):
    """Select breakdown type."""

    bd_type: str  # brakes | wheel | battery | motor | frame | electronics | other


class BreakdownConfirmCB(CallbackData, prefix="bd_cf"):
    """Confirm or cancel breakdown creation."""

    action: str  # save | cancel


class BreakdownSkipPhotoCB(CallbackData, prefix="bd_skip"):
    """Skip photo upload or finish uploading."""

    action: str  # skip | done


class BreakdownHistoryCB(CallbackData, prefix="bd_hist"):
    """View breakdown history for a bike."""

    bike_id: int


class BreakdownDetailCB(CallbackData, prefix="bd_detail"):
    """View a single breakdown's detail (with photos)."""

    breakdown_id: int
    bike_id: int


class BreakdownCourierSelectCB(CallbackData, prefix="bd_cr"):
    """Manually select a courier for the breakdown."""

    courier_id: int


# ── Repair (Stage 5) ──────────────────────────────────────────────────


class RepairMenuCB(CallbackData, prefix="rp_menu"):
    """Navigation within the repair sub-menu."""

    action: str  # pickup | complete | my_repairs | back


class RepairBikeSelectCB(CallbackData, prefix="rp_bike"):
    """Select a bike for repair pickup."""

    bike_id: int
    store_id: int


class RepairBreakdownSelectCB(CallbackData, prefix="rp_bd"):
    """Link repair to an existing breakdown."""

    breakdown_id: int


class RepairBreakdownSkipCB(CallbackData, prefix="rp_bd_skip"):
    """Skip linking repair to a breakdown."""

    action: str  # skip


class RepairMechanicSelectCB(CallbackData, prefix="rp_mech"):
    """Select a mechanic for the repair."""

    mechanic_id: int


class RepairPickupConfirmCB(CallbackData, prefix="rp_pcf"):
    """Confirm or cancel repair pickup."""

    action: str  # save | cancel


class RepairSelectCB(CallbackData, prefix="rp_sel"):
    """Select an active repair to complete or view."""

    repair_id: int


class RepairCompleteConfirmCB(CallbackData, prefix="rp_ccf"):
    """Confirm or cancel repair completion."""

    action: str  # save | cancel


# ── Registration & Roles (Stage 9) ──────────────────────────────────────


class RegistrationCB(CallbackData, prefix="reg"):
    """Registration flow actions."""

    action: str  # apply | cancel


class AdminApprovalCB(CallbackData, prefix="adm_apr"):
    """Admin approves or rejects a registration request."""

    user_id: int
    action: str  # approve | reject


class AdminRoleSelectCB(CallbackData, prefix="adm_role"):
    """Admin assigns a role to the user."""

    user_id: int
    role: str  # supervisor | mechanic


# ── Dashboard (Stage 6) ──────────────────────────────────────────────


class DashboardMenuCB(CallbackData, prefix="dash_menu"):
    """Navigation within the dashboard."""

    action: str  # open | back


class DashboardStoreCB(CallbackData, prefix="dash_store"):
    """Drill-down into a specific store."""

    store_id: int


# ── Analytics (Stage 7) ──────────────────────────────────────────────


class AnalyticsMenuCB(CallbackData, prefix="an_menu"):
    """Navigation within analytics reports."""

    action: str


class AnalyticsStoreCB(CallbackData, prefix="an_store"):
    """Store filter for analytics reports."""

    report: str  # breakdowns_month
    store_id: int  # 0 = all


# ── Courier shift (Stage 11) ────────────────────────────────────────────


class CourierMenuCB(CallbackData, prefix="cr_menu"):
    """Navigation within the courier shift menu."""

    action: str  # take | return | back


class CourierTakeConfirmCB(CallbackData, prefix="cr_take"):
    """Confirm or cancel taking a bike."""

    bike_id: int
    action: str  # save | cancel


class CourierStoreSelectCB(CallbackData, prefix="cr_store"):
    """Courier selects a store."""

    store_id: int


class CourierBikeSelectCB(CallbackData, prefix="cr_bike"):
    """Courier selects a bike from the list."""

    bike_id: int


class CourierReturnConfirmCB(CallbackData, prefix="cr_retc"):
    """Confirm returning a bike."""

    shift_bike_id: int
    confirm: bool
