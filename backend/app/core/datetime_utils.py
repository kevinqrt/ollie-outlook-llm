from datetime import datetime
from zoneinfo import ZoneInfo

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

LOCAL_TZ = ZoneInfo("Europe/Berlin")


def format_datetime_de(dt: datetime) -> str:
    """Format as 'Wochentag, TT.MM.JJJJ HH:MM' with a German weekday name.

    Converts to Europe/Berlin local time first - `dt` is normally a UTC instant
    (Graph is always queried with `Prefer: outlook.timezone="UTC"`), and showing
    the raw UTC hour to the user would be off by 1-2 hours depending on DST.
    Uses a fixed weekday lookup instead of `strftime('%A', ...)` since that
    depends on the process locale, which isn't guaranteed to be German on every host.
    """
    local = dt.astimezone(LOCAL_TZ)
    return f"{WEEKDAYS_DE[local.weekday()]}, {local.strftime('%d.%m.%Y %H:%M')}"
