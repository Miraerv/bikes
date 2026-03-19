"""BIKE-32 — Auto-close stale usage logs.

Closes usage logs where `ended_at IS NULL` and `started_at` is older than
the configured threshold (default: 12 hours).
"""

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select, update

from app.db.base import market_session_maker
from app.db.models.bike_usage_log import BikeUsageLog

AUTO_CLOSE_HOURS = 12


async def auto_close_stale_logs() -> None:
    """Find and close stale usage logs (started > N hours ago, not ended)."""
    threshold = datetime.now() - timedelta(hours=AUTO_CLOSE_HOURS)

    async with market_session_maker() as session:
        # Find stale logs for logging
        stale_result = await session.execute(
            select(BikeUsageLog)
            .where(
                BikeUsageLog.ended_at.is_(None),
                BikeUsageLog.started_at < threshold,
            ),
        )
        stale_logs = stale_result.scalars().all()

        if not stale_logs:
            logger.debug("Auto-close: no stale logs found.")
            return

        stale_ids = [log.id for log in stale_logs]

        # Bulk update
        await session.execute(
            update(BikeUsageLog)
            .where(BikeUsageLog.id.in_(stale_ids))
            .values(ended_at=datetime.now()),
        )
        await session.commit()

        logger.info(
            "Auto-close: closed {count} stale usage logs (IDs: {ids})",
            count=len(stale_ids),
            ids=stale_ids,
        )
