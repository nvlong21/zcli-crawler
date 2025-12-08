from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    """Returns the current datetime object, timezone-aware (UTC)."""
    return datetime.now(timezone.utc)

def make_aware(dt: datetime, tz: timezone = timezone.utc) -> datetime:
    """Makes a naive datetime object timezone-aware (defaults to UTC)."""
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        # Already aware
        return dt
    # Assume naive datetime is in the specified timezone (usually UTC)
    return dt.replace(tzinfo=tz)

def format_datetime_iso(dt: datetime) -> str:
    """Formats a datetime object into an ISO 8601 string with Z for UTC."""
    if dt.tzinfo is None:
        dt = make_aware(dt, timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)

    # Format with 'Z' for UTC timezone identifier, including milliseconds
    return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def parse_datetime_iso(dt_str: str) -> Optional[datetime]:
    """
    Parses an ISO 8601 formatted string (including 'Z' or offset)
    into a timezone-aware datetime object (normalized to UTC).
    Returns None if parsing fails.
    """
    if not isinstance(dt_str, str):
        logger.debug(f"Cannot parse non-string type '{type(dt_str).__name__}' as datetime.")
        return None
    try:
        # Handle 'Z' explicitly for broader compatibility before parsing
        if dt_str.endswith('Z'):
            dt_str_normalized = dt_str[:-1] + '+00:00'
        else:
            dt_str_normalized = dt_str

        # datetime.fromisoformat handles most ISO 8601 formats
        dt = datetime.fromisoformat(dt_str_normalized)

        # Normalize to UTC if it has timezone info
        if dt.tzinfo:
             return dt.astimezone(timezone.utc)
        else:
             # If parsed as naive, assume UTC (make this assumption explicit)
             logger.debug(f"Parsed datetime string '{dt_str}' as naive, assuming UTC.")
             return make_aware(dt, timezone.utc)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse datetime string '{dt_str}': {e}")
        return None # Return None if parsing fails

def to_timestamp_ms(dt: datetime) -> int:
    """Converts a datetime object to a UTC timestamp in milliseconds (integer)."""
    if dt.tzinfo is None:
        dt = make_aware(dt, timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    # Convert to float timestamp (seconds) and then to milliseconds (int)
    return int(dt.timestamp() * 1000)

def from_timestamp_ms(ts_ms: int) -> Optional[datetime]:
    """Converts a UTC timestamp in milliseconds (integer) to a timezone-aware datetime object."""
    if not isinstance(ts_ms, int):
         logger.warning(f"Invalid type for millisecond timestamp: {type(ts_ms).__name__}")
         return None
    try:
        # Convert milliseconds to seconds (float)
        ts_sec = ts_ms / 1000.0
        return datetime.fromtimestamp(ts_sec, tz=timezone.utc)
    except (ValueError, OverflowError, OSError) as e: # Catch potential errors fromtimestamp
        logger.error(f"Failed to convert millisecond timestamp {ts_ms}: {e}")
        return None
