from aiogram import Router

from app.bot.handlers.add_bike import router as add_bike_router
from app.bot.handlers.analytics import router as analytics_router
from app.bot.handlers.bike_card import router as bike_card_router
from app.bot.handlers.breakdown import router as breakdown_router
from app.bot.handlers.change_status import router as change_status_router
from app.bot.handlers.courier_shift import router as courier_shift_router
from app.bot.handlers.dashboard import router as dashboard_router
from app.bot.handlers.decommission import router as decommission_router
from app.bot.handlers.list_bikes import router as list_bikes_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.registration import router as registration_router
from app.bot.handlers.repair import router as repair_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.usage import router as usage_router

router = Router(name="main")
router.include_router(start_router)
router.include_router(registration_router)
router.include_router(menu_router)
router.include_router(add_bike_router)
router.include_router(list_bikes_router)
router.include_router(bike_card_router)
router.include_router(change_status_router)
router.include_router(decommission_router)
router.include_router(usage_router)
router.include_router(breakdown_router)
router.include_router(repair_router)
router.include_router(dashboard_router)
router.include_router(analytics_router)
router.include_router(courier_shift_router)

__all__ = ["router"]
