# tests/test_models.py
from chroniclemap.core.models import (
    Campaign,
    FilterType,
    GameDate,
    Rank,
    RankPeriod,
    new_campaign,
    new_ruler,
    new_snapshot,
)


def test_snapshot_roundtrip_and_campaign_serialization(tmp_path):
    # create campaign
    camp = new_campaign("Test Campaign", path=str(tmp_path))

    # add snapshot with various dates (BCE, ancient, future)
    snap_bce = new_snapshot(
        date_str="-0100-03-15",  # BCE 100
        filter_type=FilterType.REALMS,
        path="maps/Realms/-0100-03-15.png",
    )
    snap_ancient = new_snapshot(
        date_str="1024-06-15",  # ~1000 years ago from present
        filter_type=FilterType.FAITH,
        path="maps/Faith/1024-06-15.png",
    )
    snap_future = new_snapshot(
        date_str="3024-09-20",  # ~1000 years in future
        filter_type=FilterType.CULTURE,
        path="maps/Culture/3024-09-20.png",
    )
    camp.add_snapshot(snap_bce)
    camp.add_snapshot(snap_ancient)
    camp.add_snapshot(snap_future)

    # add ruler with BCE and far future dates
    ruler = new_ruler(
        full_name="Alexander",
        display_name="Alex",
        start_date="-0336-07-20",  # BCE 336
        end_date="3024-12-31",  # Far future
    )
    rp = RankPeriod(
        from_date=GameDate(-100, 1, 1),  # BCE period
        to_date=GameDate(1024, 12, 31),  # Ancient period end
        rank=Rank.KINGDOM,
        note="Ancient times",
    )
    ruler.rank_periods.append(rp)
    camp.rulers.append(ruler)

    # serialize to dict and json
    d = camp.to_dict()
    j = camp.to_json()

    # load back
    camp2 = Campaign.from_json(j)
    camp3 = Campaign.from_dict(d)

    # checks
    assert camp2.name == camp.name
    assert len(camp2.snapshots) == 3

    # Check BCE date preserved
    assert camp2.snapshots[0].date.year == -100
    assert camp2.snapshots[0].date.month == 3
    assert camp2.snapshots[0].date.day == 15

    # Check ancient date preserved (~1000 years ago)
    assert camp2.snapshots[1].date.year == 1024
    assert camp2.snapshots[1].date.month == 6
    assert camp2.snapshots[1].date.day == 15

    # Check future date preserved (~1000 years future)
    assert camp2.snapshots[2].date.year == 3024

    # Check ruler dates with BCE
    assert camp2.rulers[0].start_date.year == -336
    assert camp2.rulers[0].end_date.year == 3024

    # Check RankPeriod dates
    assert camp2.rulers[0].rank_periods[0].from_date.year == -100

    assert camp3.name == camp.name
    assert len(camp3.snapshots) == 3


def test_date_parsing_various_formats():
    # BCE dates
    d1 = GameDate.fromiso("-0100-11-11")
    assert d1.year == -100
    assert d1.month == 11
    assert d1.day == 11
    assert d1.to_iso() == "-0100-11-11"

    # Ancient dates (~1000 years ago)
    d2 = GameDate.fromiso("1024-05-20")
    assert d2.year == 1024
    assert d2.to_iso() == "1024-05-20"

    # Future dates (~1000 years from now)
    d3 = GameDate.fromiso("3024-08-15")
    assert d3.year == 3024

    # Various separators
    assert GameDate.fromiso("867-11-11").to_iso() == "0867-11-11"
    assert GameDate.fromiso("867.11.11").to_iso() == "0867-11-11"
    assert GameDate.fromiso("867/11/11").to_iso() == "0867-11-11"
    assert GameDate.fromiso("867.11").to_iso() == "0867-11-01"
    assert GameDate.fromiso("867").to_iso() == "0867-01-01"

    # Test BCE with various formats
    assert GameDate.fromiso("-044-03").to_iso() == "-0044-03-01"  # BCE 44
    assert GameDate.fromiso("-1000").to_iso() == "-1000-01-01"  # BCE 1000


def test_date_arithmetic_bce_and_wide_range():
    """Test arithmetic works across BCE and CE boundaries and wide year ranges"""
    # BCE date arithmetic
    bce_date = GameDate(-100, 3, 15)

    # Add days within same year
    d2 = bce_date.add_days(20)
    assert d2.year == -100
    assert d2.month == 4  # April
    assert d2.day == 4  # 15 + 20 = 35, March has 31 days, so April 4th

    # Difference between BCE and CE dates
    d_bce = GameDate(-1, 12, 31)
    d_ce = GameDate(1, 1, 1)
    diff_forward = d_bce.days_until(d_ce)
    assert diff_forward == 1  # Just one day apart

    # Test ~1000 years apart (ancient to modern)
    ancient = GameDate(1024, 6, 15)
    modern = GameDate(2024, 6, 15)
    days_diff = ancient.days_until(modern)
    # Roughly 1000 * 365.25 = 365250 days, accounting for leap years
    assert 365000 < days_diff < 366000

    # Test ~1000 years into future (modern to future)
    future = GameDate(3024, 6, 15)
    days_future = modern.days_until(future)
    assert 365000 < days_future < 366000

    # Test arithmetic across the BCE/CE boundary with add_days
    transition = GameDate(-1, 12, 30)
    plus_5 = transition.add_days(5)
    assert plus_5.year == 1
    assert plus_5.month == 1
    assert plus_5.day == 4
