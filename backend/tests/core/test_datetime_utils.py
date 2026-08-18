from datetime import UTC, datetime

from app.core.datetime_utils import format_datetime_de


def test_format_datetime_de_uses_german_weekday_names():
    # 2026-08-03 is a Monday. August is CEST (UTC+2), so 09:05 UTC -> 11:05 local.
    monday = datetime(2026, 8, 3, 9, 5, tzinfo=UTC)

    assert format_datetime_de(monday) == "Montag, 03.08.2026 11:05"


def test_format_datetime_de_covers_all_weekdays():
    expected = [
        "Montag",
        "Dienstag",
        "Mittwoch",
        "Donnerstag",
        "Freitag",
        "Samstag",
        "Sonntag",
    ]
    for offset, name in enumerate(expected):
        day = datetime(2026, 8, 3 + offset, 12, 0, tzinfo=UTC)
        assert format_datetime_de(day).startswith(name)


def test_format_datetime_de_converts_summer_time_utc_plus_2():
    # August is CEST (UTC+2).
    summer = datetime(2026, 8, 6, 14, 22, tzinfo=UTC)

    assert format_datetime_de(summer) == "Donnerstag, 06.08.2026 16:22"


def test_format_datetime_de_converts_winter_time_utc_plus_1():
    # January is CET (UTC+1).
    winter = datetime(2026, 1, 8, 14, 22, tzinfo=UTC)

    assert format_datetime_de(winter) == "Donnerstag, 08.01.2026 15:22"
