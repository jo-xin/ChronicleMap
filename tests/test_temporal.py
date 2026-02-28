# tests/test_temporal.py
from chroniclemap.core.models import FilterType
from chroniclemap.core.models import GameDate as date
from chroniclemap.core.models import new_campaign, new_snapshot
from chroniclemap.temporal.engine import TemporalEngine


def test_engine_seek_and_get_snapshot():
    camp = new_campaign("tmp", path=None)
    # add a few snapshots
    s1 = new_snapshot(
        date_str="1444-01-01",
        filter_type=FilterType.REALMS,
        path="maps/realms/1444-01-01.png",
    )
    s2 = new_snapshot(
        date_str="1445-06-01",
        filter_type=FilterType.REALMS,
        path="maps/realms/1445-06-01.png",
    )
    s3 = new_snapshot(
        date_str="1446-01-01",
        filter_type=FilterType.CULTURE,
        path="maps/culture/1446-01-01.png",
    )
    camp.add_snapshot(s1)
    camp.add_snapshot(s2)
    camp.add_snapshot(s3)

    engine = TemporalEngine(campaign=camp)
    # seek to 1445-06-01 exact
    engine.seek(date(1445, 6, 1))
    cur = engine.get_current_date()
    assert cur == date(1445, 6, 1)

    # exact snapshot for REALMS
    snap = engine.get_snapshot_for(date(1445, 6, 1), filter_type=FilterType.REALMS)
    assert snap is not None and snap.date == date(1445, 6, 1)

    # for a date between s1 and s2, prefer_latest_before should return s1
    snap2 = engine.get_snapshot_for(date(1445, 1, 1), filter_type=FilterType.REALMS)
    assert snap2 is not None and snap2.date == date(1444, 1, 1)


def test_engine_tick_ignore_leap_years():
    """
    Test no-leap calendar mode (ignore_leap_years=True).
    In this mode, every year has exactly 365 days, February always has 28 days.
    """
    camp = new_campaign("no-leap-test", path=None)
    engine = TemporalEngine(campaign=camp, ignore_leap_years=True)
    engine.set_playback_speed("days/sec", 1.0)

    # Test 1: 365 days from 2000-01-01 should reach 2001-01-01
    # (2000 is treated as 365 days, not 366)
    engine.seek(date(2000, 1, 1))
    engine.tick(365.0)
    assert engine.get_current_date() == date(
        2001, 1, 1
    ), "In no-leap mode, 2000 should have 365 days"

    # Test 2: Verify February never has 29th in no-leap mode
    # Advance from Feb 28 to Mar 1 should be 1 day (no Feb 29 in between)
    engine.seek(date(2000, 2, 28))
    engine.tick(1.0)
    assert engine.get_current_date() == date(
        2000, 3, 1
    ), "In no-leap mode, Feb 28 + 1 day should be Mar 1 (no leap day)"

    # Test 3: Multi-year advancement consistency
    # 3 years = 3 * 365 = 1095 days
    engine.seek(date(2000, 1, 1))
    engine.tick(1095.0)
    assert engine.get_current_date() == date(
        2003, 1, 1
    ), "3 years in no-leap mode should be exactly 1095 days"


def test_engine_tick_respect_leap_years():
    """
    Test standard calendar mode (ignore_leap_years=False).
    Respects actual leap years (2000 is a leap year, 2001 is not).
    """
    camp = new_campaign("leap-test", path=None)
    engine = TemporalEngine(campaign=camp, ignore_leap_years=False)
    engine.set_playback_speed("days/sec", 1.0)

    # Test 1: From leap year 2000, advancing 365 days lands on 2000-12-31
    # (because 2000 has 366 days, day 365 is Dec 31, not Jan 1 of next year)
    engine.seek(date(2000, 1, 1))
    engine.tick(365.0)
    assert engine.get_current_date() == date(
        2000, 12, 31
    ), "In leap year 2000, day 365 should be Dec 31, not Jan 1 2001"

    # Test 2: Advancing 366 days from 2000-01-01 reaches 2001-01-01
    engine.seek(date(2000, 1, 1))
    engine.tick(366.0)
    assert engine.get_current_date() == date(
        2001, 1, 1
    ), "366 days needed to cross a leap year boundary"

    # Test 3: From common year 2001, 365 days reaches 2002-01-01 exactly
    engine.seek(date(2001, 1, 1))
    engine.tick(365.0)
    assert engine.get_current_date() == date(
        2002, 1, 1
    ), "Common year 2001 should advance 365 days to next year"

    # Test 4: Verify Feb 29 exists in leap year mode
    engine.seek(date(2000, 2, 28))
    engine.tick(1.0)
    assert engine.get_current_date() == date(
        2000, 2, 29
    ), "In standard mode, Feb 28 + 1 day should be Feb 29 in leap year 2000"

    engine.tick(1.0)
    assert engine.get_current_date() == date(
        2000, 3, 1
    ), "Feb 29 + 1 day should be Mar 1"


def test_engine_tick_fractional_days():
    """Test that fractional day advancement works correctly in both modes."""
    # No-leap mode
    camp = new_campaign("frac-test", path=None)
    engine = TemporalEngine(campaign=camp, ignore_leap_years=True)
    engine.set_playback_speed("days/sec", 0.5)  # 0.5 days per second

    engine.seek(date(2000, 1, 1))
    engine.tick(2.0)  # 2 seconds * 0.5 days/sec = 1 day
    assert engine.get_current_date() == date(2000, 1, 2)

    # Standard mode
    engine2 = TemporalEngine(campaign=camp, ignore_leap_years=False)
    engine2.set_playback_speed("days/sec", 0.5)
    engine2.seek(date(2000, 1, 1))
    engine2.tick(2.0)
    assert engine2.get_current_date() == date(2000, 1, 2)


def test_engine_playback_speed_variations():
    """
    Test that different playback speeds correctly affect time advancement.
    Also verifies year boundary crossing with correct speed settings.
    """
    camp = new_campaign("speed-test", path=None)

    # Test 1: Speed = 1 day/second, tick 1 second = 1 day advancement
    engine = TemporalEngine(campaign=camp, ignore_leap_years=True)
    engine.set_playback_speed("days/sec", 1.0)
    engine.seek(date(2000, 12, 31))
    engine.tick(1.0)
    assert engine.get_current_date() == date(
        2001, 1, 1
    ), "Speed 1.0: 1 second tick should advance 1 day"

    # Test 2: Speed = 365 days/second, tick 1 second = 365 days (1 year)
    engine.seek(date(2000, 12, 31))  # Reset
    engine.set_playback_speed("days/sec", 365.0)
    engine.tick(1.0)
    assert engine.get_current_date() == date(
        2001, 12, 31
    ), "Speed 365.0: 1 second tick should advance 365 days (1 year)"

    # Test 3: Speed = 0.5 days/second, tick 2 seconds = 1 day
    engine.seek(date(2000, 6, 15))
    engine.set_playback_speed("days/sec", 0.5)
    engine.tick(2.0)
    assert engine.get_current_date() == date(
        2000, 6, 16
    ), "Speed 0.5: 2 seconds tick should advance 1 day"

    # Test 4: Speed = 10 days/second, tick 0.1 seconds = 1 day (fractional seconds)
    engine.seek(date(2000, 3, 1))
    engine.set_playback_speed("days/sec", 10.0)
    engine.tick(0.1)  # 0.1 * 10 = 1 day
    assert engine.get_current_date() == date(
        2000, 3, 2
    ), "Speed 10.0: 0.1 seconds tick should advance 1 day"

    # Test 5: Standard leap-year mode with speed verification
    engine_std = TemporalEngine(campaign=camp, ignore_leap_years=False)
    engine_std.set_playback_speed("days/sec", 1.0)
    engine_std.seek(date(2000, 2, 28))
    engine_std.tick(1.0)
    assert engine_std.get_current_date() == date(
        2000, 2, 29
    ), "Standard mode with speed 1.0 should respect leap days"
