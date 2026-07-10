from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

TRADING_TIMEZONE = ZoneInfo("Asia/Dhaka")


def trading_now() -> datetime:
    """Return the current trading timestamp in Bangladesh time."""
    return datetime.now(timezone.utc).astimezone(TRADING_TIMEZONE)


def trading_date(moment: datetime | None = None) -> date:
    """Return the Bangladesh trading date for a timestamp or for now."""
    current = moment or trading_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(TRADING_TIMEZONE).date()


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    """Parse persisted timestamps, treating legacy naive values as UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_on_trading_date(value: str | datetime | None, target: date) -> bool:
    parsed = parse_timestamp(value)
    return parsed is not None and trading_date(parsed) == target
