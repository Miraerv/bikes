import asyncio

from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.bot import create_dispatcher
from app.bot.handlers.alerts import (
    check_frequent_breakdowns,
    check_long_repairs,
    check_low_bikes,
)
from app.bot.handlers.auto_close import auto_close_stale_logs
from app.core.config import settings
from app.core.logging import setup_logging
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
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_close_stale_logs, "interval", hours=1)

    # Alert cron tasks (BIKE-80..84)
    alert_interval = settings.alert_check_minutes
    scheduler.add_job(check_low_bikes, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(check_long_repairs, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(
        check_frequent_breakdowns, "interval", minutes=alert_interval, args=[bot],
    )

    scheduler.start()
    logger.info(
        "Scheduler started: auto_close every 1h, alerts every {m}min",
        m=alert_interval,
    )

    # Start internal HTTP API
    api_app = create_api_app(bot)
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.api_port)
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

