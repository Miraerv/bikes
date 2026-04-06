"""Internal HTTP API for receiving signals from the Laravel backend.

Runs an aiohttp server alongside aiogram polling.
Endpoint: POST /api/signal
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from loguru import logger
from sqlalchemy import select, text

from app.core.config import settings
from app.db.base import market_session_maker
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.courier_shift import CourierShift

if TYPE_CHECKING:
    from aiogram import Bot


def _check_auth(request: web.Request) -> bool:
    """Validate Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == settings.api_token


async def _get_telegram_ids_by_roles(
    roles: list[str],
) -> list[int]:
    """Fetch telegram_ids of users with given roles."""
    async with market_session_maker() as session:
        result = await session.execute(
            select(BotUser.telegram_id).where(BotUser.role.in_(roles)),
        )
        return [row[0] for row in result.all()]


async def _get_courier_telegram_id(admin_user_id: int) -> int | None:
    """Find courier's telegram_id by admin_user_id."""
    async with market_session_maker() as session:
        result = await session.execute(
            select(BotUser.telegram_id).where(
                BotUser.admin_user_id == admin_user_id,
            ),
        )
        row = result.one_or_none()
        return row[0] if row else None


_COURIER_SHIFT_ORDERS_QUERY = text("""
    SELECT
        TIMESTAMPDIFF(MINUTE, bosc.accepted_at, bosc.completed_at) AS full_time_minutes,
        bdd.layer
    FROM
        boom_link_couriers_orders blco
        INNER JOIN boom_order_details bod ON blco.order_id = bod.id
        INNER JOIN boom_orders_status_changes bosc ON bod.id = bosc.order_id
        LEFT JOIN boom_delivery_details bdd ON bod.id = bdd.order_id
    WHERE
        blco.admin_user_id = :admin_user_id
        AND bod.type = 'customer'
        AND bod.status = 'completed'
        AND bosc.completed_at BETWEEN :shift_start AND :shift_end
        AND bdd.layer IN (1, 2)
""")


def _get_sla_emoji(sla: float) -> str:
    if sla >= 95:
        return "🟢"
    if sla >= 90:
        return "🟡"
    return "🔴"


async def _get_shift_stats(
    shift_id: int,
    admin_user_id: int,
) -> tuple[str, int, float | None]:
    """Return (courier_name, total_orders, sla%) for a finished shift."""
    async with market_session_maker() as session:
        # courier name
        admin = await session.get(AdminUser, admin_user_id)
        name = f"{admin.name} {admin.surname or ''}".strip() if admin else str(admin_user_id)

        # shift timestamps
        shift = await session.get(CourierShift, shift_id)
        if not shift or not shift.shift_end:
            return name, 0, None

        # orders for this courier during shift
        rows = (
            await session.execute(
                _COURIER_SHIFT_ORDERS_QUERY,
                {
                    "admin_user_id": admin_user_id,
                    "shift_start": shift.shift_start,
                    "shift_end": shift.shift_end,
                },
            )
        ).all()

        if not rows:
            return name, 0, None

        total = 0
        good = 0
        for full_time, layer in rows:
            layer = int(layer) if layer is not None else 0
            minutes = full_time or 0
            total += 1
            if (layer == 1 and minutes <= 45) or (layer == 2 and minutes <= 60):
                good += 1

        sla = (good / total * 100) if total else None
        return name, total, sla


async def _handle_shift_ended(bot: Bot, payload: dict) -> None:
    """Send shift-ended notifications to courier, admin, and supervisors."""
    admin_user_id = payload.get("admin_user_id")
    shift_id = payload.get("shift_id")

    if not admin_user_id:
        logger.warning("shift_ended signal missing admin_user_id")
        return

    name, total_orders, sla = await _get_shift_stats(shift_id, admin_user_id)

    msg = (
        f"🔔 <b>Смена завершена</b>\n\n"
        f"📋 Смена: <b>#{shift_id}</b>\n"
        f"👤 Курьер: <b>{name}</b>\n\n"
        f"<b>Итоги смены:</b>\n"
        f"📦 Заказов: <b>{total_orders}</b>\n"
    )
    if sla is not None:
        msg += f"📊 SLA: <b>{sla:.1f}%</b> {_get_sla_emoji(sla)}"
    else:
        msg += "📊 SLA: <b>—</b>"

    # TODO: добавить курьера и супервайзеров после тестирования
    recipients: list[int] = [settings.admin_telegram_id]

    for tg_id in recipients:
        try:
            await bot.send_message(chat_id=tg_id, text=msg)
        except Exception:
            logger.exception(
                "Failed to send shift_ended notification to {tg_id}",
                tg_id=tg_id,
            )

    logger.info(
        "shift_ended: notified {count} recipients for shift #{shift_id}",
        count=len(recipients),
        shift_id=shift_id,
    )


SIGNAL_HANDLERS = {
    "shift_ended": _handle_shift_ended,
}


def create_api_app(bot: Bot) -> web.Application:
    """Create the aiohttp application with signal endpoint."""

    async def handle_signal(request: web.Request) -> web.Response:
        if not _check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        signal = data.get("signal")
        payload = data.get("payload", {})

        if not signal:
            return web.json_response({"error": "missing signal"}, status=400)

        handler = SIGNAL_HANDLERS.get(signal)
        if not handler:
            return web.json_response(
                {"error": f"unknown signal: {signal}"}, status=400,
            )

        try:
            await handler(bot, payload)
        except Exception:
            logger.exception("Error handling signal {signal}", signal=signal)
            return web.json_response({"error": "internal error"}, status=500)

        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/api/signal", handle_signal)
    return app
