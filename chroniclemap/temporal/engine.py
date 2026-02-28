# chroniclemap/temporal/engine.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Union

from chroniclemap.core.models import Campaign, FilterType, GameDate, Snapshot


@dataclass
class TemporalEngine:
    campaign: Campaign
    current_date: GameDate | None = None
    playing: bool = False
    on_time_update: Optional[Callable[[GameDate], None]] = None
    # new flag: if True, ignore real-world leap years and treat each year as 365 days
    ignore_leap_years: bool = True

    def __post_init__(self):
        if self.current_date is None:
            if self.campaign.snapshots:
                self.current_date = self.campaign.snapshots[0].date
            else:
                now = datetime.now(timezone.utc)
                self.current_date = GameDate(now.year, now.month, now.day)

    # playback controls
    def set_playback_speed(self, unit: str, value: float):

        self.campaign.config.playback_speed = {"units": unit, "value": value}

    def get_playback_speed(self) -> dict:
        return self.campaign.config.playback_speed

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def seek(self, to_date: Union[str, GameDate]):
        self.current_date = GameDate.fromiso(to_date)
        if self.on_time_update:
            self.on_time_update(self.current_date)

    def get_current_date(self) -> GameDate:
        return self.current_date

    def tick(self, dt_seconds: float):
        """
        Advance internal clock by dt_seconds * playback_rate (days/sec).
        If ignore_leap_years is True, use no-leap ordinal arithmetic.
        """
        ps = self.get_playback_speed()
        units = ps.get("units", "days/sec")
        value = float(ps.get("value", 1.0))

        if units == "years/sec":
            value *= 365 if self.ignore_leap_years else 365.2425
        elif units == "months/sec":
            value *= 30  # Simplified, real implementation should consider calendar
        elif units == "days/sec":
            pass
        else:
            raise ValueError(f"Invalid playback unit: {units}")

        days_advance = value * float(dt_seconds)

        # convert current date to ordinal (0-based)
        cur_ord = self.current_date.to_ordinal(ignore_leap=self.ignore_leap_years)
        new_ord = int(round(cur_ord + days_advance))
        self.current_date = GameDate.from_ordinal(
            new_ord, ignore_leap=self.ignore_leap_years
        )

        if self.on_time_update:
            self.on_time_update(self.current_date)

    # snapshot selection helpers (unchanged)
    def get_snapshot_for(
        self,
        d: GameDate,
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
        self, d: GameDate, filter_type: Optional[FilterType] = None
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
    ) -> Optional[GameDate]:
        cur = self.get_current_date()
        nxt = self.next_snapshot_after(cur, filter_type=filter_type)
        if nxt is None:
            return None
        self.seek(nxt.date)
        return nxt.date
