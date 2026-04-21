import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from loguru import logger

from app.bot import create_dispatcher
from app.bot.handlers.alerts import (
    check_frequent_breakdowns,
    check_long_repairs,
    check_low_bikes,
    check_no_online_couriers,
)
from app.bot.handlers.auto_close import auto_close_stale_logs
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tz import YAKUTSK_TZ
from app.internal_api import create_api_app


async def main() -> None:
    """Application entry point."""
    setup_logging()
    logger.info("Starting Bikes Bot...")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = create_dispatcher()

    # Start scheduler
    scheduler = AsyncIOScheduler(timezone=YAKUTSK_TZ)
    scheduler.add_job(auto_close_stale_logs, "interval", hours=1)

    # Alert cron tasks (BIKE-80..84)
    alert_interval = settings.alert_check_minutes
    scheduler.add_job(check_low_bikes, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(check_long_repairs, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(
        check_frequent_breakdowns, "interval", minutes=alert_interval, args=[bot],
    )
    scheduler.add_job(
        check_no_online_couriers,
        "cron",
        hour=8,
        minute=15,
        args=[bot, "08:15"],
        id="check_no_online_couriers_0815",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=900,
    )
    scheduler.add_job(
        check_no_online_couriers,
        "cron",
        hour=16,
        minute=15,
        args=[bot, "16:15"],
        id="check_no_online_couriers_1615",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=900,
    )

    scheduler.start()
    logger.info(
        "Scheduler started: auto_close every 1h, alerts every {m}min, "
        "no-online-courier at 08:15/16:15 Asia/Yakutsk",
        m=alert_interval,
    )

    # Start internal HTTP API
    api_app = create_api_app(bot)
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.api_port)  # noqa: S104
    await site.start()
    logger.info("Internal API started on port {port}", port=settings.api_port)

    # Skip pending updates on startup
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
