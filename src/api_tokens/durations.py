"""Parse human-friendly expiry values for the management commands."""

import re
from datetime import date, datetime, time, timedelta

from django.utils import timezone

DURATION_PATTERN = re.compile(r"^(\d+)([hdwy])$")
UNIT_DAYS = {"d": 1, "w": 7, "y": 365}


def parse_expiry(value: str, now: datetime | None = None) -> datetime:
    """Turn ``90d`` / ``12h`` / ``2w`` / ``1y`` or an ISO date into an aware datetime.

    A bare date means the end of that day in the current time zone, so ``2027-01-31``
    still works on 31 January.

    Args:
        value: Relative duration or ISO 8601 date/datetime.
        now: Reference time for relative values; defaults to ``timezone.now()``.

    Returns:
        The expiry moment.

    Raises:
        ValueError: If the value is neither form, or lies in the past.
    """
    now = now or timezone.now()
    match = DURATION_PATTERN.match(value.strip().lower())
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount * UNIT_DAYS[unit])
        expires = now + delta
    else:
        expires = _parse_absolute(value.strip())
    if expires <= now:
        raise ValueError(f"Expiry {value!r} is not in the future.")
    return expires


def _parse_absolute(value: str) -> datetime:
    """Parse an ISO date or datetime, making it time-zone aware.

    Args:
        value: ISO 8601 string.

    Returns:
        Aware datetime.

    Raises:
        ValueError: If the string is not ISO 8601.
    """
    try:
        parsed: datetime = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Expected e.g. 90d, 12h, 2w, 1y or an ISO date, got {value!r}.") from None
    if len(value) == len("YYYY-MM-DD"):
        parsed = datetime.combine(date.fromisoformat(value), time.max)
    return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
