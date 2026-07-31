from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.config import settings


def _load_tz(name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError):
        try:
            import tzdata  # noqa: F401
            return ZoneInfo(name)
        except ImportError:
            pass
    return timezone.utc


# Globally cache ZoneInfo objects
APP_TIMEZONE = getattr(settings, 'APP_TIMEZONE', "Asia/Kolkata")
TZ_IST = _load_tz(APP_TIMEZONE if APP_TIMEZONE else "Asia/Kolkata")
TZ_UTC = _load_tz("UTC")

def get_ist_now() -> datetime:
    """Returns the current timezone-aware datetime in Asia/Kolkata (IST)."""
    return datetime.now(TZ_IST)

def get_utc_now() -> datetime:
    """Returns the current timezone-aware datetime in UTC (internal storage standard)."""
    return datetime.now(TZ_UTC)

def to_ist(dt: datetime) -> datetime:
    """Safely converts any datetime (naive or aware) to Asia/Kolkata (IST)."""
    if not dt:
        return dt
    if dt.tzinfo is None:
        # Assume naive timestamps in DB were written in UTC
        dt = dt.replace(tzinfo=TZ_UTC)
    return dt.astimezone(TZ_IST)

def format_ist(dt: datetime) -> str:
    """Formats a datetime into a standard Indian Standard Time format."""
    if not dt:
        return ""
    return to_ist(dt).strftime("%d-%m-%Y %I:%M %p")
