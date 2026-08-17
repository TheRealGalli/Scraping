from datetime import datetime
import pytz
from config import settings

def get_rome_time() -> datetime:
    """Returns current datetime in Europe/Rome timezone."""
    rome_tz = pytz.timezone(settings.TIMEZONE)
    return datetime.now(rome_tz)

def is_night_time(dt: datetime = None) -> bool:
    """
    Checks if the given time (or current Rome time) falls within anti-night filter window.
    Night window: 22:00 to 06:00 (Europe/Rome).
    Returns True if execution should be skipped.
    """
    if dt is None:
        dt = get_rome_time()
    
    hour = dt.hour
    # Night window: 22:00 to 05:59 (hour >= 22 or hour < 6)
    if hour >= settings.NIGHT_START_HOUR or hour < settings.NIGHT_END_HOUR:
        return True
    return False

def is_sender_operating_hours(dt: datetime = None) -> bool:
    """
    Checks if current time (Europe/Rome) falls within daytime email sending window (06:00 to 22:00).
    Returns True if sending is allowed.
    """
    if dt is None:
        dt = get_rome_time()
    
    hour = dt.hour
    # Daytime window: 06:00 to 21:59 (6 <= hour < 22)
    if settings.NIGHT_END_HOUR <= hour < settings.NIGHT_START_HOUR:
        return True
    return False
