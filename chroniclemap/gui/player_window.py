from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.storage.manager import StorageManager
from chroniclemap.temporal.engine import TemporalEngine


class PlayerWindow(QWidget):
    """
    ChronicleMap 播放主界面（第一版原型）：
    - 中央：当前帧地图预览
    - 底部：时间轴滑块（可拖动），下方预留帝王时间轴位
    - 左侧：播放控制（播放/暂停、倍速、上一帧/下一帧）
    - 右侧：基础元数据展示（当前日期、当前滤镜等，占位）
    """

    def __init__(
        self,
        campaign_name: str,
        storage_base_dir,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.storage = StorageManager(storage_base_dir)

        # 加载 campaign 并初始化时间轴引擎
        self.campaign = self.storage.load_campaign(campaign_name)
        self.engine = TemporalEngine(campaign=self.campaign)

        self.setWindowTitle(f"ChronicleMap — Player — {campaign_name}")
        self.resize(1200, 800)

        root = QHBoxLayout(self)

        # 左侧：播放控制
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
        self.speed_spin.setValue(
            float(self.campaign.config.playback_speed.get("value", 365))
        )
        speed_row.addWidget(QLabel("Speed (days/sec):"))
        speed_row.addWidget(self.speed_spin)

        left.addWidget(self.play_btn)
        left.addWidget(self.pause_btn)
        left.addWidget(self.prev_btn)
        left.addWidget(self.next_btn)
        left.addLayout(speed_row)
        left.addStretch()

        # 中央：画布 + 时间轴
        center = QVBoxLayout()
        root.addLayout(center, 3)

        self.image_label = QLabel("No snapshots yet")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)
        center.addWidget(self.image_label, 5)

        # 时间轴滑块
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setSingleStep(1)
        self.timeline_slider.setPageStep(10)

        self.timeline_label = QLabel("Timeline")

        center.addWidget(self.timeline_slider)
        center.addWidget(self.timeline_label)

        # 预留的帝王进度条（暂时只是占位）
        self.ruler_timeline = QSlider(Qt.Horizontal)
        self.ruler_timeline.setEnabled(False)
        center.addWidget(QLabel("Ruler timeline (planned)"))
        center.addWidget(self.ruler_timeline)

        # 右侧：当前状态 / 元数据占位
        right = QVBoxLayout()
        root.addLayout(right, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([f.value for f in FilterType])
        right.addWidget(QLabel("Filter:"))
        right.addWidget(self.filter_combo)

        self.current_date_label = QLabel("")
        self.current_snapshot_label = QLabel("")
        right.addWidget(QLabel("Current date:"))
        right.addWidget(self.current_date_label)
        right.addWidget(QLabel("Current snapshot:"))
        right.addWidget(self.current_snapshot_label)
        right.addStretch()

        # 播放计时器：定期调用 TemporalEngine.tick
        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25fps
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        # 信号绑定
        self.play_btn.clicked.connect(self._on_play)
        self.pause_btn.clicked.connect(self._on_pause)
        self.prev_btn.clicked.connect(self._on_prev_snapshot)
        self.next_btn.clicked.connect(self._on_next_snapshot)
        self.speed_spin.valueChanged.connect(self._on_speed_changed)
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        self.filter_combo.currentTextChanged.connect(lambda _txt: self._update_frame())

        # 根据当前快照范围初始化时间轴
        self._init_timeline_range()
        self._update_frame()

    # ------------------------------------------------------------------
    # 初始化/辅助
    # ------------------------------------------------------------------

    def _init_timeline_range(self) -> None:
        """根据 campaign 中快照的日期范围设置时间轴滑块范围。"""
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

    # ------------------------------------------------------------------
    # 槽函数：播放控制
    # ------------------------------------------------------------------

    def _on_play(self) -> None:
        self.engine.play()

    def _on_pause(self) -> None:
        self.engine.pause()

    def _on_prev_snapshot(self) -> None:
        """跳到前一个快照（按当前滤镜）。"""
        cur = self.engine.get_current_date()
        flt = self._current_filter()
        # 找到当前日期之前的最大一张
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
        """使用 TemporalEngine 的 step_to_next_snapshot。"""
        flt = self._current_filter()
        nxt = self.engine.step_to_next_snapshot(filter_type=flt)
        if nxt:
            self._update_frame()

    def _on_speed_changed(self, value: float) -> None:
        self.engine.set_playback_speed("days_per_second", float(value))

    def _on_slider_changed(self, value: int) -> None:
        """用户拖动时间轴时，将当前日期设置为对应 ordinal。"""
        if not hasattr(self, "_ord_min"):
            return
        gd = GameDate.from_ordinal(value, ignore_leap=False)
        self.engine.seek(gd)
        self._update_frame()

    def _on_tick(self) -> None:
        """定时器回调：若当前处于播放状态，则推进时间并刷新画面。"""
        if not self.engine.playing:
            return
        dt_seconds = self._timer.interval() / 1000.0
        self.engine.tick(dt_seconds)
        self._update_frame()

    # ------------------------------------------------------------------
    # 画面更新
    # ------------------------------------------------------------------

    def _update_frame(self) -> None:
        """根据当前日期和滤镜，找到合适的快照并更新预览/标签/时间轴。"""
        cur_date = self.engine.get_current_date()
        flt = self._current_filter()
        snap = self.engine.get_snapshot_for(
            d=cur_date, filter_type=flt, prefer_latest_before=True
        )

        # 更新时间轴和标签
        if hasattr(self, "_ord_min"):
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(cur_date.to_ordinal(False))
            self.timeline_slider.blockSignals(False)
        self._update_timeline_label()
        self.current_date_label.setText(cur_date.to_iso())

        if snap:
            self.current_snapshot_label.setText(snap.path)
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
        cur = self.engine.get_current_date()
        self.timeline_label.setText(
            f"Timeline: {d_min.to_iso()} … {d_max.to_iso()}  |  current: {cur.to_iso()}"
        )
