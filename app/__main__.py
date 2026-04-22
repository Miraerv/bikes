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
from app.bot.handlers.daily_courier_report import send_daily_courier_report
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tz import YAKUTSK_TZ
from app.internal_api import create_api_app

NO_ONLINE_COURIER_SLOTS = ("08:15", "16:15")
NO_ONLINE_COURIER_MISFIRE_GRACE_SECONDS = 900
DAILY_COURIER_REPORT_MISFIRE_GRACE_SECONDS = 3600


def _schedule_no_online_courier_check(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    slot: str,
) -> None:
    """Schedule one no-online-courier control slot."""
    hour, minute = (int(part) for part in slot.split(":", maxsplit=1))
    scheduler.add_job(
        check_no_online_couriers,
        "cron",
        hour=hour,
        minute=minute,
        args=[bot, slot],
        id=f"check_no_online_couriers_{hour:02d}{minute:02d}",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=NO_ONLINE_COURIER_MISFIRE_GRACE_SECONDS,
    )


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
    scheduler.add_job(
        send_daily_courier_report,
        "cron",
        hour=0,
        minute=0,
        args=[bot],
        id="send_daily_courier_report",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=DAILY_COURIER_REPORT_MISFIRE_GRACE_SECONDS,
    )

    # Alert cron tasks (BIKE-80..84)
    alert_interval = settings.alert_check_minutes
    scheduler.add_job(check_low_bikes, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(check_long_repairs, "interval", minutes=alert_interval, args=[bot])
    scheduler.add_job(
        check_frequent_breakdowns,
        "interval",
        minutes=alert_interval,
        args=[bot],
    )
    for slot in NO_ONLINE_COURIER_SLOTS:
        _schedule_no_online_courier_check(scheduler, bot, slot)

    scheduler.start()
    logger.info(
        "Scheduler started: auto_close every 1h, alerts every {m}min, "
        "daily courier report at 00:00, no-online-courier at {slots} Asia/Yakutsk",
        m=alert_interval,
        slots="/".join(NO_ONLINE_COURIER_SLOTS),
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
