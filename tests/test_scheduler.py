from datetime import UTC, datetime

from wkx_beacon.scheduler import needs_catch_up

SCHEDULE = "0 7 * * *"
TZ = "Pacific/Auckland"
# 4 July 2026 09:12 NZST is 3 July 21:12 UTC; the 07:00 NZST fire was missed.
NOW = datetime(2026, 7, 3, 21, 12, tzinfo=UTC)


def test_never_ran_needs_catch_up() -> None:
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=None, now=NOW) is True


def test_missed_fire_needs_catch_up() -> None:
    two_days_ago = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=two_days_ago, now=NOW) is True


def test_recent_run_does_not_need_catch_up() -> None:
    after_last_fire = datetime(2026, 7, 3, 19, 30, tzinfo=UTC)  # 07:30 NZST 4 July
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=after_last_fire, now=NOW) is False
