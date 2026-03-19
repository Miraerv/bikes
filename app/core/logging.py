import logging
import sys

from loguru import logger

from app.core.config import settings


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging → loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        # Find caller from where originated the logged message.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """Configure loguru as the single logging sink."""
    # Remove default loguru handler
    logger.remove()

    # Console output
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File output with rotation
    logger.add(
        "logs/bot.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
    )

    # Intercept stdlib logging (aiogram, sqlalchemy, etc.)
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for logger_name in ("aiogram", "sqlalchemy.engine", "alembic"):
        logging.getLogger(logger_name).handlers = [_InterceptHandler()]
