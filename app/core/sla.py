from __future__ import annotations

from typing import Final

MAX_DELIVERY_MINUTES_BY_LAYER: Final[dict[int, int]] = {
    1: 45,
    2: 60,
}


def get_sla_emoji(sla: float) -> str:
    if sla >= 95:
        return "🟢"
    if sla >= 90:
        return "🟡"
    return "🔴"


def is_sla_eligible_layer(layer: int | None) -> bool:
    return layer in MAX_DELIVERY_MINUTES_BY_LAYER


def is_order_within_sla(layer: int, minutes: int) -> bool:
    max_minutes = MAX_DELIVERY_MINUTES_BY_LAYER.get(layer)
    return max_minutes is not None and minutes <= max_minutes


def order_row_is_within_sla(full_time: int | None, layer: int | None) -> bool:
    normalized_layer = int(layer) if layer is not None else 0
    minutes = full_time or 0
    return is_order_within_sla(normalized_layer, minutes)
