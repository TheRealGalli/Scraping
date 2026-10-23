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
    Checks weekday sender window; scraper hours are configured separately.
    Returns True if sending is allowed.
    """
    if dt is None:
        dt = get_rome_time()
    
    dt = dt.astimezone(pytz.timezone(settings.TIMEZONE))
    def minutes(value):
        hour, minute = map(int, value.split(":"))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Invalid sender time")
        return hour * 60 + minute
    return dt.weekday() < 5 and minutes(settings.SENDER_START_TIME) <= dt.hour * 60 + dt.minute < minutes(settings.SENDER_END_TIME)
