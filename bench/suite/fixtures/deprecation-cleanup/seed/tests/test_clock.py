from datetime import datetime

from clock.stamps import age_seconds


def test_age_seconds_between_two_times():
    then = datetime(2024, 1, 1, 12, 0, 0)
    now = datetime(2024, 1, 1, 12, 1, 30)
    assert age_seconds(then, now) == 90.0


def test_age_seconds_is_zero_for_same_time():
    moment = datetime(2024, 3, 10, 8, 0)
    assert age_seconds(moment, moment) == 0.0


def test_age_seconds_across_days():
    assert age_seconds(datetime(2024, 1, 1), datetime(2024, 1, 3)) == 172800.0
