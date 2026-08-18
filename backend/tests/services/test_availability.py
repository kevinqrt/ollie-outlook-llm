from datetime import UTC, datetime, timedelta

from app.api.schemas.calendar_schema import CalendarEventSchema
from app.services.availability import _compute_free_slots, _round_up_to_quarter_hour


def test_round_up_to_quarter_hour_rounds_up_unaligned_time():
    unaligned = datetime(2026, 8, 6, 16, 23, 7, tzinfo=UTC)

    assert _round_up_to_quarter_hour(unaligned) == datetime(2026, 8, 6, 16, 30, tzinfo=UTC)


def test_round_up_to_quarter_hour_leaves_aligned_time_unchanged():
    aligned = datetime(2026, 8, 6, 16, 30, tzinfo=UTC)

    assert _round_up_to_quarter_hour(aligned) == aligned


def test_compute_free_slots_daily_window_none_allows_any_hour():
    """Regression guard: daily_window=None (the default) must behave exactly
    like before this feature existed - no restriction on the hour of day."""
    window_start = datetime(2026, 8, 3, 22, 0, tzinfo=UTC)
    window_end = window_start + timedelta(hours=2)

    slots = _compute_free_slots([], window_start, window_end, duration_minutes=30)

    assert slots
    assert slots[0].start == window_start


def test_compute_free_slots_skips_fully_busy_day_when_daily_window_set():
    # daily_window=(8, 12) is local Europe/Berlin time; August is CEST (UTC+2),
    # so local 08:00-12:00 is UTC 06:00-10:00.
    busy = [
        CalendarEventSchema(
            id="busy-1",
            subject="Busy",
            start=datetime(2026, 8, 3, 6, 0, tzinfo=UTC),  # 08:00 local
            end=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),  # 12:00 local
            organizer=None,
            is_organizer=False,
        )
    ]
    window_start = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)  # 08:00 local, Aug 3
    window_end = datetime(2026, 8, 5, 6, 0, tzinfo=UTC)  # 08:00 local, Aug 5

    slots = _compute_free_slots(
        busy, window_start, window_end, duration_minutes=30, daily_window=(8, 12)
    )

    assert slots
    # Aug 3's entire morning window is busy -> first free slot must be Aug 4's
    # morning (08:00 local = 06:00 UTC), not Aug 3 afternoon/evening.
    assert slots[0].start == datetime(2026, 8, 4, 6, 0, tzinfo=UTC)
    assert all(6 <= s.start.hour < 10 for s in slots)


def test_compute_free_slots_skips_slot_that_would_spill_past_daily_window_end():
    # Only 15 minutes remain before the local 12:00 boundary (11:45-12:00), but
    # duration is 30 minutes - must not be suggested, must jump to next day.
    busy = [
        CalendarEventSchema(
            id="busy-1",
            subject="Busy",
            start=datetime(2026, 8, 3, 6, 0, tzinfo=UTC),  # 08:00 local
            end=datetime(2026, 8, 3, 9, 45, tzinfo=UTC),  # 11:45 local
            organizer=None,
            is_organizer=False,
        )
    ]
    window_start = datetime(2026, 8, 3, 6, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 5, 6, 0, tzinfo=UTC)

    slots = _compute_free_slots(
        busy, window_start, window_end, duration_minutes=30, daily_window=(8, 12)
    )

    assert slots
    assert slots[0].start == datetime(2026, 8, 4, 6, 0, tzinfo=UTC)
