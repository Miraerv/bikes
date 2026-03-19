"""Global timezone configuration — Yakutsk (UTC+9).

DB writes use server time (datetime.now()).
User-facing display uses Yakutsk timezone.
"""

from datetime import datetime, timedelta, timezone

YAKUTSK_TZ = timezone(timedelta(hours=9), name="Asia/Yakutsk")


def now_display() -> datetime:
    """Return current datetime in Yakutsk timezone (for display only)."""
    return datetime.now(tz=YAKUTSK_TZ)


def to_yakutsk(dt: datetime | None) -> datetime:
    """Convert a naive (server-local) datetime to Yakutsk for display.

    If the datetime is already timezone-aware, it is simply converted.
    If naive, it is assumed to be in the server's local timezone.
    If None, returns current Yakutsk time as a safe fallback.
    """
    if dt is None:
        return now_display()
    if dt.tzinfo is None:
        # Assume server-local time → attach local tz, then convert
        dt = dt.astimezone()  # attach system tz
    return dt.astimezone(YAKUTSK_TZ)
