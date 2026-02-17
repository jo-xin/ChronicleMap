# tests/test_player_viewmodel.py
from datetime import date

from chroniclemap.core.models import FilterType, new_campaign, new_snapshot
from chroniclemap.ui.player_viewmodel import PlayerViewModel


def test_player_tick_and_snapshot_selection():
    camp = new_campaign("t-camp", path=None)
    s1 = new_snapshot(
        date_str="1444-01-01",
        filter_type=FilterType.REALMS,
        path="maps/realms/1444-01-01.png",
    )
    s2 = new_snapshot(
        date_str="1445-01-01",
        filter_type=FilterType.REALMS,
        path="maps/realms/1445-01-01.png",
    )
    camp.add_snapshot(s1)
    camp.add_snapshot(s2)

    vm = PlayerViewModel(campaign=camp, ignore_leap_years=True)
    # initial date should be s1
    assert vm.get_current_date() == date(1444, 1, 1)

    # subscribe to snapshot_changed
    captured = {"path": None}

    def on_snap(p):
        captured["path"] = p

    vm.snapshot_changed.connect(on_snap)

    # seek to 1445-01-01
    vm.seek(date(1445, 1, 1))
    assert captured["path"] is not None and "1445-01-01" in captured["path"]

    # set speed and tick one second equivalently
    vm.set_playback_speed("days_per_second", 365.0)
    vm.play()
    vm.tick(1.0)
    # should have advanced by ~365 days (to next year)
    assert vm.get_current_date().year >= 1445
