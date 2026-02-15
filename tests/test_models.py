# tests/test_models.py
from datetime import date

from chroniclemap.core.models import (
    Campaign,
    FilterType,
    Rank,
    RankPeriod,
    new_campaign,
    new_ruler,
    new_snapshot,
)


def test_snapshot_roundtrip_and_campaign_serialization(tmp_path):
    # create campaign
    camp = new_campaign("Test Campaign", path=str(tmp_path))

    # add snapshot
    snap = new_snapshot(
        date_str="1444-11-11",
        filter_type=FilterType.REALMS,
        path="maps/Realms/1444-11-11.png",
    )
    camp.add_snapshot(snap)

    # add ruler
    ruler = new_ruler(
        full_name="John Doe",
        display_name="John",
        start_date="1440-01-01",
        end_date="1450-01-01",
    )
    rp = RankPeriod(
        from_date=date(1440, 1, 1),
        to_date=date(1450, 1, 1),
        rank=Rank.KINGDOM,
        note="Initial",
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
    assert len(camp2.snapshots) == 1
    assert camp2.snapshots[0].date == snap.date
    assert camp2.rulers and camp2.rulers[0].full_name == "John Doe"

    assert camp3.name == camp.name
    assert len(camp3.snapshots) == 1
    assert camp3.snapshots[0].date == snap.date
    assert camp3.rulers and camp3.rulers[0].full_name == "John Doe"


def test_date_parsing_various_formats():
    # different formats accepted
    from chroniclemap.core.models import _ensure_date

    assert _ensure_date("1444-11-11").isoformat() == "1444-11-11"
    assert _ensure_date("1444.11.11").isoformat() == "1444-11-11"
    assert _ensure_date("14441111").isoformat() == "1444-11-11"
    assert _ensure_date("1444/11/11").isoformat() == "1444-11-11"
    assert _ensure_date("1444.11").isoformat() == "1444-11-01"
    assert _ensure_date("1444").isoformat() == "1444-01-01"
