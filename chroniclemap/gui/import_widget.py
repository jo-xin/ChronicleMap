# chroniclemap/gui/import_widget.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# use GameDate and FilterType from core.models
from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.gui.snapshot_confirm import SnapshotConfirmDialog
from chroniclemap.storage.manager import StorageManager


class ImportWidget(QWidget):
    def __init__(
        self,
        campaign_name: str,
        campaign_store,
        storage_manager: StorageManager,
        ocr_provider,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.store = campaign_store
        self.storage = storage_manager
        self.ocr = ocr_provider

        self.setAcceptDrops(True)
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("Import Snapshot"))

        # filter radio group: read from metadata (list of strings or FilterType)
        meta = self.store.load_metadata(campaign_name) or {}
        meta_filters = meta.get("filters")
        if not meta_filters:
            # fallback to all FilterType values
            meta_filters = [f.value for f in FilterType]
        else:
            # normalize to strings
            meta_filters = [
                f.value if isinstance(f, FilterType) else str(f) for f in meta_filters
            ]

        self.filter_group = QButtonGroup(self)
        rg = QGroupBox("Filter")
        rg_layout = QHBoxLayout()
        self.filter_buttons = []
        for i, f in enumerate(meta_filters):
            rb = QRadioButton(f)
            if i == 0:
                rb.setChecked(True)
            self.filter_group.addButton(rb)
            self.filter_buttons.append(rb)
            rg_layout.addWidget(rb)
        rg.setLayout(rg_layout)
        layout.addWidget(rg)

        # default interval
        interval_box = QGroupBox("Default interval for next snapshot")
        ib_layout = QHBoxLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setValue(1)
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["years", "months", "days"])
        ib_layout.addWidget(self.interval_spin)
        ib_layout.addWidget(self.interval_unit)
        interval_box.setLayout(ib_layout)
        layout.addWidget(interval_box)

        # import buttons
        btn_layout = QHBoxLayout()
        self.file_btn = QPushButton("Choose File...")
        self.paste_btn = QPushButton("Paste (Ctrl+V)")
        btn_layout.addWidget(self.file_btn)
        btn_layout.addWidget(self.paste_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # wire
        self.file_btn.clicked.connect(self.on_choose_file)
        self.paste_btn.clicked.connect(self.on_paste)

        # store filters locally
        self._filters = meta_filters

    def current_filter(self) -> str:
        for rb in self.filter_buttons:
            if rb.isChecked():
                return rb.text()
        return self._filters[0]

    def on_choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select image", str(Path.home()), "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._handle_input_path(Path(path))

    def on_paste(self):
        clipboard = QGuiApplication.clipboard()
        md: QMimeData = clipboard.mimeData()
        if md.hasImage():
            img = clipboard.image()
            # write to tmp file
            tmp = (
                Path(tempfile.gettempdir())
                / f"chroniclemap_clip_{int(os.times()[4]*1000)}.png"
            )
            pix = QPixmap.fromImage(img)
            pix.save(str(tmp), "PNG")
            self._handle_input_path(tmp)
        else:
            self.status_label.setText("Clipboard has no image")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self._handle_input_path(Path(path))

    def _handle_input_path(self, path: Path):
        self.status_label.setText("Processing...")
        detected_date = None
        _detected_conf = None

        # OCR处理
        try:
            if self.ocr:
                # 直接使用manager需要的OCR参数格式
                raw_date = self.ocr.extract_date(
                    path,
                    roi_spec=None,  # 根据实际需要传递ROI参数
                    template_key=None,  # 根据OCR模板选择
                )
                detected_date = raw_date if raw_date else None
        except Exception:
            # logger.warning(f"OCR failed: {e}")
            detected_date = None

        # 后备逻辑：基于最后一个快照预测
        if not detected_date:
            last_snap = self._get_last_snapshot(self.current_filter())
            if last_snap:
                try:
                    num = int(self.interval_spin.value())
                    unit = self.interval_unit.currentText()
                    predicted = self._add_interval_iso(
                        last_snap.date.to_iso(), num, unit
                    )
                    detected_date = predicted
                except Exception:
                    detected_date = None

        # 获取当前Campaign对象（关键修改点）
        try:
            campaign = self.storage.load_campaign(self.campaign_name)
        except FileNotFoundError:
            self.status_label.setText("Campaign not found")
            return

        # 对话框配置
        filters = [f.value for f in FilterType]  # 使用核心枚举类型
        dlg = SnapshotConfirmDialog(
            self.window(),
            path,
            self.campaign_name,
            filters,
            detected_date_iso=detected_date,
        )

        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_result()
            try:
                # 使用storage/manager.py的接口规范（关键修改）
                snap = self.storage.import_image(
                    campaign=campaign,
                    src_path=path,
                    filter_type=FilterType(data["filter"]),  # 转换为枚举类型
                    date_str=data["date"],
                    ocr_provider=self.ocr,  # 传递OCR组件
                    create_dirs_if_missing=True,  # 确保目录创建
                )

                # 更新UI状态
                self.status_label.setText(f"Imported snapshot {snap.date}")
                self.snapshot_added.emit(snap)  # 如果需要触发信号

            except ValueError as ve:  # 处理枚举转换错误
                self.status_label.setText(f"Invalid filter: {str(ve)}")
            except Exception as e:
                self.status_label.setText(f"Import failed: {e}")
        else:
            self.status_label.setText("Import cancelled")

    def _get_last_snapshot_date(self, filter_name: str) -> Optional[str]:
        meta = self.store.load_metadata(self.campaign_name) or {}
        snaps = meta.get("snapshots", [])
        dates = [
            s.get("date")
            for s in snaps
            if s.get("filter") == filter_name and s.get("date")
        ]
        if not dates:
            return None
        return max(dates)

    def _add_interval_iso(self, iso_date: str, num: int, unit: str) -> str:
        """
        Use GameDate arithmetic for predicting the next date.
        Unit: 'days', 'months', 'years'
        """
        gd = GameDate.fromiso(iso_date)
        if unit == "days":
            nd = gd + int(num)  # uses GameDate.__add__ (days)
            return nd.to_iso()
        elif unit == "months":
            # naive month addition: adjust year/month and clamp day
            y, m, d = gd.year, gd.month, gd.day
            total = (m - 1) + num
            ny = y + (total // 12)
            nm = (total % 12) + 1
            # clamp day to month length via GameDate constructor
            try:
                nd = GameDate(ny, nm, d)
            except Exception:
                # clamp to last day of month
                import calendar

                mdays = calendar.monthrange(ny, nm)[1]
                nd = GameDate(ny, nm, mdays)
            return nd.to_iso()
        else:  # years
            y, m, d = gd.year, gd.month, gd.day
            ny = y + int(num)
            try:
                nd = GameDate(ny, m, d)
            except Exception:
                # clamp feb 29 -> feb 28 if needed
                nd = GameDate(ny, m, min(d, 28))
            return nd.to_iso()
