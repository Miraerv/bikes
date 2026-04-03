"""Internal HTTP API for receiving signals from the Laravel backend.

Runs an aiohttp server alongside aiogram polling.
Endpoint: POST /api/signal
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.db.base import market_session_maker
from app.db.models.bot_user import BotUser, UserRole

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


async def _handle_shift_ended(bot: Bot, payload: dict) -> None:
    """Send shift-ended notifications to courier, admin, and supervisors."""
    admin_user_id = payload.get("admin_user_id")
    shift_id = payload.get("shift_id")

    if not admin_user_id:
        logger.warning("shift_ended signal missing admin_user_id")
        return

    msg = (
        f"🔔 <b>Смена завершена</b>\n\n"
        f"📋 Смена: <b>#{shift_id}</b>\n"
        f"👤 ID курьера: <b>{admin_user_id}</b>"
    )

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
