"""Inline keyboard builders grouped by bot flow.

This package keeps the historical ``app.bot.keyboards.builders`` import path as
the public facade, while the actual builders live in smaller flow modules.
"""

from __future__ import annotations

from app.bot.keyboards.builders.analytics import (
    analytics_back_kb as analytics_back_kb,
)
from app.bot.keyboards.builders.analytics import (
    analytics_menu_kb as analytics_menu_kb,
)
from app.bot.keyboards.builders.bikes import (
    ITEMS_PER_PAGE as ITEMS_PER_PAGE,
)
from app.bot.keyboards.builders.bikes import (
    add_bike_confirm_kb as add_bike_confirm_kb,
)
from app.bot.keyboards.builders.bikes import (
    bike_card_actions_kb as bike_card_actions_kb,
)
from app.bot.keyboards.builders.bikes import (
    bike_card_kb as bike_card_kb,
)
from app.bot.keyboards.builders.bikes import (
    bike_list_kb as bike_list_kb,
)
from app.bot.keyboards.builders.bikes import (
    bike_menu_kb as bike_menu_kb,
)
from app.bot.keyboards.builders.bikes import (
    bike_status_select_kb as bike_status_select_kb,
)
from app.bot.keyboards.builders.bikes import (
    confirm_decommission_kb as confirm_decommission_kb,
)
from app.bot.keyboards.builders.bikes import (
    status_filter_kb as status_filter_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_bike_select_kb as breakdown_bike_select_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_confirm_kb as breakdown_confirm_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_courier_select_kb as breakdown_courier_select_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_detail_kb as breakdown_detail_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_history_kb as breakdown_history_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_menu_kb as breakdown_menu_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_photo_kb as breakdown_photo_kb,
)
from app.bot.keyboards.builders.breakdown import (
    breakdown_type_kb as breakdown_type_kb,
)
from app.bot.keyboards.builders.common import (
    main_menu_kb as main_menu_kb,
)
from app.bot.keyboards.builders.common import (
    store_select_kb as store_select_kb,
)
from app.bot.keyboards.builders.courier import (
    courier_menu_kb as courier_menu_kb,
)
from app.bot.keyboards.builders.courier import (
    courier_take_confirm_kb as courier_take_confirm_kb,
)
from app.bot.keyboards.builders.dashboard import (
    dashboard_back_kb as dashboard_back_kb,
)
from app.bot.keyboards.builders.dashboard import (
    dashboard_stores_kb as dashboard_stores_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_active_list_kb as repair_active_list_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_bike_select_kb as repair_bike_select_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_breakdown_select_kb as repair_breakdown_select_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_complete_confirm_kb as repair_complete_confirm_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_mechanic_select_kb as repair_mechanic_select_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_menu_kb as repair_menu_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_my_list_kb as repair_my_list_kb,
)
from app.bot.keyboards.builders.repair import (
    repair_pickup_confirm_kb as repair_pickup_confirm_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_active_logs_kb as usage_active_logs_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_active_store_select_kb as usage_active_store_select_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_bike_select_kb as usage_bike_select_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_confirm_take_kb as usage_confirm_take_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_courier_select_kb as usage_courier_select_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_menu_kb as usage_menu_kb,
)
from app.bot.keyboards.builders.usage import (
    usage_return_confirm_kb as usage_return_confirm_kb,
)

__all__ = [
    "ITEMS_PER_PAGE",
    "add_bike_confirm_kb",
    "analytics_back_kb",
    "analytics_menu_kb",
    "bike_card_actions_kb",
    "bike_card_kb",
    "bike_list_kb",
    "bike_menu_kb",
    "bike_status_select_kb",
    "breakdown_bike_select_kb",
    "breakdown_confirm_kb",
    "breakdown_courier_select_kb",
    "breakdown_detail_kb",
    "breakdown_history_kb",
    "breakdown_menu_kb",
    "breakdown_photo_kb",
    "breakdown_type_kb",
    "confirm_decommission_kb",
    "courier_menu_kb",
    "courier_take_confirm_kb",
    "dashboard_back_kb",
    "dashboard_stores_kb",
    "main_menu_kb",
    "repair_active_list_kb",
    "repair_bike_select_kb",
    "repair_breakdown_select_kb",
    "repair_complete_confirm_kb",
    "repair_mechanic_select_kb",
    "repair_menu_kb",
    "repair_my_list_kb",
    "repair_pickup_confirm_kb",
    "status_filter_kb",
    "store_select_kb",
    "usage_active_logs_kb",
    "usage_active_store_select_kb",
    "usage_bike_select_kb",
    "usage_confirm_take_kb",
    "usage_courier_select_kb",
    "usage_menu_kb",
    "usage_return_confirm_kb",
]
