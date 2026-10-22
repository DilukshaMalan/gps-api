"""Parsing and validating query parameters."""
import re
from datetime import datetime

from app.core.errors import ApiError

_SPACE_BEFORE_OFFSET = re.compile(r" \d{2}:\d{2}$")


def parse_instant(raw: str | None, name: str) -> datetime:
    """ISO 8601 instant WITH a UTC offset, e.g. 2026-10-14T00:00:00+05:30 (or ...Z).

    A '+' that was not percent-encoded in the URL arrives as a space; that is repaired here so
    clients that forget to send %2B still work.
    """
    if raw is None or not raw.strip():
        raise ApiError(400, "invalid_request", f"Query parameter '{name}' is required.")
    value = raw.strip()
    if _SPACE_BEFORE_OFFSET.search(value):
        value = value[:-6] + "+" + value[-5:]
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ApiError(400, "invalid_request",
                       f"'{name}' must be an ISO 8601 date-time, e.g. 2026-10-14T00:00:00+05:30.")
    if parsed.tzinfo is None:
        raise ApiError(400, "invalid_request", f"'{name}' must include a UTC offset, e.g. +05:30 or Z.")
    return parsed


def parse_bool(raw: str | None, name: str, default: bool = False) -> bool:
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    raise ApiError(400, "invalid_request", f"'{name}' must be true or false.")


def parse_max_points(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, "invalid_request", "'maxPoints' must be an integer.")
    if not 50 <= value <= 50_000:
        raise ApiError(400, "invalid_request", "'maxPoints' must be between 50 and 50000.")
    return value
