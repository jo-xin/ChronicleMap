# chroniclemap/ui/player_viewmodel.py
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QObject, Signal

from chroniclemap.core.models import Campaign, FilterType
from chroniclemap.temporal.engine import TemporalEngine


class PlayerViewModel(QObject):
    """
    QObject wrapper around TemporalEngine for UI binding.

    Signals:
      - time_changed(date)  -> emitted when engine time updates
      - snapshot_changed(str|None) -> emitted when currently visible snapshot path changes
      - playing_changed(bool)
    """

    time_changed = Signal(object)  # emits datetime.date
    snapshot_changed = Signal(object)  # emits snapshot path (str) or None
    playing_changed = Signal(bool)

    def __init__(self, campaign: Campaign, ignore_leap_years: bool = True):
        super().__init__()
        self.campaign = campaign
        self.engine = TemporalEngine(
            campaign=campaign, ignore_leap_years=ignore_leap_years
        )
        self._current_snapshot_id: Optional[str] = None

    # --- playback controls ---
    def play(self):
        self.engine.play()
        self.playing_changed.emit(True)

    def pause(self):
        self.engine.pause()
        self.playing_changed.emit(False)

    def set_playback_speed(self, units: str, value: float):
        self.engine.set_playback_speed(units, value)

    def seek(self, to_date: date):
        self.engine.seek(to_date)
        self._emit_time_and_snapshot()

    def get_current_date(self) -> date:
        return self.engine.get_current_date()

    # called by UI timer; dt_seconds is real seconds elapsed
    def tick(self, dt_seconds: float):
        # only advance if playing
        if not self.engine.playing:
            return
        self.engine.tick(dt_seconds)
        self._emit_time_and_snapshot()

    # --- snapshot logic ---
    def _emit_time_and_snapshot(self):
        # emit current date
        cur_date = self.engine.get_current_date()
        self.time_changed.emit(cur_date)

        # determine best snapshot for current date and selected filter
        # Note: UI provides current filter via select_filter() below
        snap = self.engine.get_snapshot_for(
            cur_date,
            filter_type=(
                self._current_filter if hasattr(self, "_current_filter") else None
            ),
        )
        if snap is None:
            path = None
            snap_id = None
        else:
            path = str(snap.path)
            snap_id = snap.id

        # only emit snapshot_changed if different snapshot
        if snap_id != self._current_snapshot_id:
            self._current_snapshot_id = snap_id
            self.snapshot_changed.emit(path)

    # UI can inform viewmodel which filter is currently selected
    def select_filter(self, filter_value: Optional[str | FilterType]):
        if filter_value is None:
            self._current_filter = None
            return
        if isinstance(filter_value, FilterType):
            self._current_filter = filter_value
        else:
            try:
                self._current_filter = FilterType(filter_value)
            except Exception:
                self._current_filter = None
        # after changing filter, we should recompute snapshot for current date
        self._emit_time_and_snapshot()

    # helper to step to next snapshot (UI action)
    def step_to_next_snapshot(self):
        next_date = self.engine.step_to_next_snapshot(
            filter_type=(
                self._current_filter if hasattr(self, "_current_filter") else None
            )
        )
        if next_date:
            self._emit_time_and_snapshot()
        return next_date
