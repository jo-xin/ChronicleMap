# chroniclemap/temporal/engine.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional

from chroniclemap.core.models import Campaign, FilterType, Snapshot

# month lengths for "no-leap" calendar
_NO_LEAP_MONTH_LENGTHS: List[int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_NO_LEAP_CUMULATIVE = [0]
_acc = 0
for m in _NO_LEAP_MONTH_LENGTHS:
    _acc += m
    _NO_LEAP_CUMULATIVE.append(_acc)


def date_to_no_leap_ordinal(d: date) -> int:
    """
    Map a date to an ordinal (0-based) in a calendar where each year = 365 days,
    and February always has 28 days.
    ordinal = (year-1) * 365 + (day_of_year_no_leap - 1)
    """
    y = d.year
    # compute day_of_year ignoring leap year
    day_of_year = _NO_LEAP_CUMULATIVE[d.month - 1] + d.day
    return (y - 1) * 365 + (day_of_year - 1)


def ordinal_to_date_no_leap(ordinal: int) -> date:
    """
    Convert an ordinal (0-based) in no-leap calendar back to date.
    """
    year = ordinal // 365 + 1
    day_of_year = (ordinal % 365) + 1
    # find month via cumulative
    month = 1
    for i in range(1, 13):
        if day_of_year <= _NO_LEAP_CUMULATIVE[i]:
            month = i
            break
    # day is day_of_year - cumulative[month-1]
    day = day_of_year - _NO_LEAP_CUMULATIVE[month - 1]
    return date(year, month, day)


@dataclass
class TemporalEngine:
    campaign: Campaign
    current_datetime: datetime | None = None
    playing: bool = False
    on_time_update: Optional[Callable[[date], None]] = None
    # new flag: if True, ignore real-world leap years and treat each year as 365 days
    ignore_leap_years: bool = True

    def __post_init__(self):
        if self.current_datetime is None:
            if self.campaign.snapshots:
                d0 = self.campaign.snapshots[0].date
                self.current_datetime = datetime(d0.year, d0.month, d0.day)
            else:
                now = datetime.utcnow()
                self.current_datetime = datetime(now.year, now.month, now.day)

    # playback controls
    def set_playback_speed(self, units: str, value: float):
        self.campaign.config.playback_speed = {"units": units, "value": value}

    def get_playback_speed(self) -> dict:
        return self.campaign.config.playback_speed

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def seek(self, to_date: date):
        if self.ignore_leap_years:
            # convert via no-leap calendar but store as datetime at midnight
            self.current_datetime = datetime(to_date.year, to_date.month, to_date.day)
        else:
            self.current_datetime = datetime(to_date.year, to_date.month, to_date.day)
        if self.on_time_update:
            self.on_time_update(self.current_datetime.date())

    def get_current_date(self) -> date:
        return self.current_datetime.date()

    def tick(self, dt_seconds: float):
        """
        Advance internal clock by dt_seconds * playback_rate (days/sec).
        If ignore_leap_years is True, use no-leap ordinal arithmetic.
        """
        ps = self.get_playback_speed()
        units = ps.get("units", "days_per_second")
        value = float(ps.get("value", 1.0))
        if units != "days_per_second":
            raise NotImplementedError(
                "Only 'days_per_second' playback unit is implemented"
            )

        days_advance = value * float(dt_seconds)

        if self.ignore_leap_years:
            # convert current date to no-leap ordinal (0-based)
            cur_date = self.get_current_date()
            cur_ord = date_to_no_leap_ordinal(cur_date)
            new_ord = int(round(cur_ord + days_advance))
            new_date = ordinal_to_date_no_leap(new_ord)
            self.current_datetime = datetime(
                new_date.year, new_date.month, new_date.day
            )
        else:
            # standard python datetime arithmetic
            delta = timedelta(days=days_advance)
            self.current_datetime = self.current_datetime + delta

        if self.on_time_update:
            self.on_time_update(self.current_datetime.date())

    # snapshot selection helpers (unchanged)
    def get_snapshot_for(
        self,
        d: date,
        filter_type: Optional[FilterType] = None,
        prefer_latest_before: bool = True,
    ) -> Optional[Snapshot]:
        for s in self.campaign.snapshots:
            if s.date == d and (filter_type is None or s.filter_type == filter_type):
                return s
        if not prefer_latest_before:
            return None
        candidates = [
            s
            for s in self.campaign.snapshots
            if s.date <= d and (filter_type is None or s.filter_type == filter_type)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.date)

    def next_snapshot_after(
        self, d: date, filter_type: Optional[FilterType] = None
    ) -> Optional[Snapshot]:
        candidates = [
            s
            for s in self.campaign.snapshots
            if s.date > d and (filter_type is None or s.filter_type == filter_type)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.date)

    def step_to_next_snapshot(
        self, filter_type: Optional[FilterType] = None
    ) -> Optional[date]:
        cur = self.get_current_date()
        nxt = self.next_snapshot_after(cur, filter_type=filter_type)
        if nxt is None:
            return None
        self.seek(nxt.date)
        return nxt.date
