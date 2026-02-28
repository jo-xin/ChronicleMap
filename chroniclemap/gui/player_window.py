from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.storage.manager import StorageManager
from chroniclemap.temporal.engine import TemporalEngine


class PlayerWindow(QWidget):
    def __init__(
        self,
        campaign_name: str,
        storage_base_dir,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.storage = StorageManager(storage_base_dir)

        self.campaign = self.storage.load_campaign(campaign_name)
        self.engine = TemporalEngine(campaign=self.campaign)

        self.setWindowTitle(f"ChronicleMap - Player - {campaign_name}")
        self.resize(1200, 800)

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        root.addLayout(left, 1)

        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.prev_btn = QPushButton("Prev snapshot")
        self.next_btn = QPushButton("Next snapshot")

        speed_row = QHBoxLayout()
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setDecimals(2)
        self.speed_spin.setRange(0.01, 10000.0)

        self.speed_unit = QComboBox()
        self.speed_unit.addItems(["days/sec", "months/sec", "years/sec"])
        speed_row.addWidget(QLabel("Speed:"))
        speed_row.addWidget(self.speed_spin)
        speed_row.addWidget(self.speed_unit)

        ps = self.campaign.config.playback_speed
        self.speed_spin.setValue(float(ps.get("value", 365)))
        saved_unit = ps.get("units", "days/sec")
        if saved_unit in ["days/sec", "months/sec", "years/sec"]:
            self.speed_unit.setCurrentText(saved_unit)

        left.addWidget(self.play_btn)
        left.addWidget(self.pause_btn)
        left.addWidget(self.prev_btn)
        left.addWidget(self.next_btn)
        left.addLayout(speed_row)
        left.addStretch()

        center = QVBoxLayout()
        root.addLayout(center, 3)

        self.image_label = QLabel("No snapshots yet")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)
        center.addWidget(self.image_label, 5)

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setSingleStep(1)
        self.timeline_slider.setPageStep(10)

        self.timeline_label = QLabel("Timeline")
        self.current_date_edit = QLineEdit()
        self.current_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.current_date_edit.setClearButtonEnabled(True)
        self.current_date_jump_btn = QPushButton("Jump")

        center.addWidget(self.timeline_slider)
        center.addWidget(self.timeline_label)

        date_jump_row = QHBoxLayout()
        date_jump_row.addWidget(QLabel("Current date:"))
        date_jump_row.addWidget(self.current_date_edit)
        date_jump_row.addWidget(self.current_date_jump_btn)
        center.addLayout(date_jump_row)

        self.ruler_timeline = QSlider(Qt.Horizontal)
        self.ruler_timeline.setEnabled(False)
        center.addWidget(QLabel("Ruler timeline (planned)"))
        center.addWidget(self.ruler_timeline)

        right = QVBoxLayout()
        root.addLayout(right, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([f.value for f in FilterType])
        right.addWidget(QLabel("Filter:"))
        right.addWidget(self.filter_combo)

        self.current_snapshot_label = QLabel("")
        self.current_snapshot_label.setMaximumWidth(400)
        self.current_snapshot_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.current_snapshot_label.setStyleSheet(
            """
            QLabel {
                qproperty-alignment: AlignLeft;
                padding: 2px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """
        )
        self.current_snapshot_label.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred
        )
        right.addWidget(QLabel("Current snapshot:"))
        right.addWidget(self.current_snapshot_label)
        right.addStretch()

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self.play_btn.clicked.connect(self._on_play)
        self.pause_btn.clicked.connect(self._on_pause)
        self.prev_btn.clicked.connect(self._on_prev_snapshot)
        self.next_btn.clicked.connect(self._on_next_snapshot)
        self.speed_spin.valueChanged.connect(
            lambda v: self._on_speed_changed(v, self.speed_unit.currentText())
        )
        self.speed_unit.currentTextChanged.connect(
            lambda u: self._on_speed_changed(self.speed_spin.value(), u)
        )
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        self.current_date_jump_btn.clicked.connect(self._on_date_jump)
        self.current_date_edit.returnPressed.connect(self._on_date_jump)
        self.filter_combo.currentTextChanged.connect(lambda _txt: self._update_frame())

        self._init_timeline_range()
        self._update_frame()

    def _init_timeline_range(self) -> None:
        if not self.campaign.snapshots:
            self.timeline_slider.setEnabled(False)
            self.timeline_label.setText("Timeline: (no snapshots)")
            return

        ordinals = [
            s.date.to_ordinal(ignore_leap=False) for s in self.campaign.snapshots
        ]
        self._ord_min = min(ordinals)
        self._ord_max = max(ordinals)
        self.timeline_slider.setEnabled(True)
        self.timeline_slider.setMinimum(self._ord_min)
        self.timeline_slider.setMaximum(self._ord_max)
        self.timeline_slider.setValue(self.engine.get_current_date().to_ordinal(False))
        self._update_timeline_label()

    def _current_filter(self) -> Optional[FilterType]:
        try:
            return FilterType(self.filter_combo.currentText())
        except Exception:
            return None

    def _on_play(self) -> None:
        self.engine.play()

    def _on_pause(self) -> None:
        self.engine.pause()

    def _on_prev_snapshot(self) -> None:
        cur = self.engine.get_current_date()
        flt = self._current_filter()
        prev = None
        for s in self.campaign.snapshots:
            if flt and s.filter_type != flt:
                continue
            if s.date < cur and (prev is None or s.date > prev.date):
                prev = s
        if prev:
            self.engine.seek(prev.date)
            self._update_frame()

    def _on_next_snapshot(self) -> None:
        flt = self._current_filter()
        nxt = self.engine.step_to_next_snapshot(filter_type=flt)
        if nxt:
            self._update_frame()

    def _on_speed_changed(self, value: float, unit: str) -> None:
        self.engine.set_playback_speed(unit, value)
        self.campaign.config.playback_speed = {"units": unit, "value": value}
        self.storage.save_campaign(self.campaign)

    def _on_slider_changed(self, value: int) -> None:
        if not hasattr(self, "_ord_min"):
            return
        gd = GameDate.from_ordinal(value, ignore_leap=False)
        self.engine.seek(gd)
        self._update_frame()

    def _on_date_jump(self) -> None:
        text = self.current_date_edit.text().strip()
        if not text:
            return
        try:
            target = GameDate.fromiso(text)
        except Exception:
            self.current_date_edit.setStyleSheet("border: 1px solid #cc3333;")
            return
        self.current_date_edit.setStyleSheet("")
        self.engine.seek(target)
        self._update_frame()

    def _on_tick(self) -> None:
        if not self.engine.playing:
            return
        dt_seconds = self._timer.interval() / 1000.0
        self.engine.tick(dt_seconds)
        self._update_frame()

    def _update_frame(self) -> None:
        cur_date = self.engine.get_current_date()
        flt = self._current_filter()
        snap = self.engine.get_snapshot_for(
            d=cur_date, filter_type=flt, prefer_latest_before=True
        )

        if hasattr(self, "_ord_min"):
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(cur_date.to_ordinal(False))
            self.timeline_slider.blockSignals(False)
        self._update_timeline_label()

        self.current_date_edit.blockSignals(True)
        self.current_date_edit.setText(cur_date.to_iso())
        self.current_date_edit.blockSignals(False)

        if snap:
            self.current_snapshot_label.setText(os.path.basename(snap.path))
            pix = QPixmap(snap.path)
            if not pix.isNull():
                pix = pix.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(pix)
            else:
                self.image_label.setText("Image not available")
        else:
            self.current_snapshot_label.setText("(no snapshot for this date)")
            self.image_label.setText("No snapshot for current date")

    def _update_timeline_label(self) -> None:
        if not hasattr(self, "_ord_min") or not hasattr(self, "_ord_max"):
            return
        d_min = GameDate.from_ordinal(self._ord_min, ignore_leap=False)
        d_max = GameDate.from_ordinal(self._ord_max, ignore_leap=False)
        self.timeline_label.setText(f"Timeline: {d_min.to_iso()} - {d_max.to_iso()}")
