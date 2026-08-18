from datetime import UTC, datetime, timedelta

from app.api.schemas.calendar_schema import CalendarEventSchema, TimeSlotSchema
from app.core.datetime_utils import LOCAL_TZ


class CalendarServiceError(RuntimeError):
    pass


_SLOT_GRID_MINUTES = 15


def _round_up_to_quarter_hour(dt: datetime) -> datetime:
    """Round up to the next :00/:15/:30/:45 mark, so suggested times look clean."""
    discard = timedelta(
        minutes=dt.minute % _SLOT_GRID_MINUTES, seconds=dt.second, microseconds=dt.microsecond
    )
    rounded = dt - discard
    if discard:
        rounded += timedelta(minutes=_SLOT_GRID_MINUTES)
    return rounded


def _snap_into_daily_window(
    dt: datetime, daily_window: tuple[int, int] | None
) -> datetime:
    """Move `dt` forward to the next instant within `daily_window` (local

    hour-of-day bounds, e.g. (8, 12) for "vormittags"), evaluated in
    Europe/Berlin local time. No-op if `daily_window` is None.
    """
    if daily_window is None:
        return dt
    start_hour, end_hour = daily_window
    local = dt.astimezone(LOCAL_TZ)
    if start_hour <= local.hour < end_hour:
        return dt
    if local.hour < start_hour:
        target_local = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    else:
        target_local = (local + timedelta(days=1)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )
    return target_local.astimezone(UTC)


def _fits_in_daily_window(
    start: datetime, end: datetime, daily_window: tuple[int, int] | None
) -> bool:
    """Whether a [start, end) slot stays entirely within the same local day's

    `daily_window`, instead of spilling into a later time of day or the next day.
    """
    if daily_window is None:
        return True
    _, end_hour = daily_window
    local_start = start.astimezone(LOCAL_TZ)
    local_end = end.astimezone(LOCAL_TZ)
    boundary = local_start.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    return local_end.date() == local_start.date() and local_end <= boundary


def _end_of_local_day_window(dt: datetime, daily_window: tuple[int, int] | None) -> datetime:
    """The instant `dt`'s local day's `daily_window` closes.

    Used to force a jump to the next day's window when a candidate slot would
    otherwise spill past the end of today's window.
    """
    if daily_window is None:
        return dt
    _, end_hour = daily_window
    local = dt.astimezone(LOCAL_TZ)
    return local.replace(hour=end_hour, minute=0, second=0, microsecond=0).astimezone(UTC)


def _compute_free_slots(
    busy_events: list[CalendarEventSchema],
    window_start: datetime,
    window_end: datetime,
    duration_minutes: int,
    max_slots: int = 5,
    daily_window: tuple[int, int] | None = None,
) -> list[TimeSlotSchema]:
    """Derive up to `max_slots` free slots of `duration_minutes` within the window.

    Busy events are merged first so overlapping/adjacent meetings are treated as a
    single blocked interval. Every returned slot starts on a quarter-hour mark
    (`_round_up_to_quarter_hour`), so suggestions read as "11:00" or "11:30"
    rather than an arbitrary "16:23" tied to the exact moment the request ran.
    If `daily_window` is given (local hour-of-day bounds, e.g. (8, 12) for
    "vormittags"), slots are only suggested within that window on each day - a
    day whose window is fully busy or too short to fit is skipped entirely
    rather than spilling into an unwanted time of day.
    """
    duration = timedelta(minutes=duration_minutes)
    busy = sorted(((e.start, e.end) for e in busy_events), key=lambda pair: pair[0])

    merged: list[tuple[datetime, datetime]] = []
    for busy_start, busy_end in busy:
        if merged and busy_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], busy_end))
        else:
            merged.append((busy_start, busy_end))

    def _advance(dt: datetime) -> datetime:
        # Round first, then snap: rounding can push a time right up to (or
        # past) the window's closing hour, so the window check must run last.
        return _snap_into_daily_window(_round_up_to_quarter_hour(dt), daily_window)

    free_slots: list[TimeSlotSchema] = []
    cursor = _advance(window_start)
    for busy_start, busy_end in merged:
        while cursor + duration <= min(busy_start, window_end) and len(free_slots) < max_slots:
            if not _fits_in_daily_window(cursor, cursor + duration, daily_window):
                cursor = _advance(_end_of_local_day_window(cursor, daily_window))
                continue
            free_slots.append(TimeSlotSchema(start=cursor, end=cursor + duration))
            cursor = _advance(cursor + duration)
        cursor = _advance(max(cursor, busy_end))
        if len(free_slots) >= max_slots:
            return free_slots

    while cursor + duration <= window_end and len(free_slots) < max_slots:
        if not _fits_in_daily_window(cursor, cursor + duration, daily_window):
            cursor = _advance(_end_of_local_day_window(cursor, daily_window))
            continue
        free_slots.append(TimeSlotSchema(start=cursor, end=cursor + duration))
        cursor = _advance(cursor + duration)

    return free_slots
