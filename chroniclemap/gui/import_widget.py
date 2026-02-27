# chroniclemap/gui/import_widget.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
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
    # 发出一个信号，通知外层“有新的 Snapshot 被导入”，载荷为 Snapshot 对象
    snapshot_added = Signal(object)
    # 当前选中的滤镜发生变化时发出（载荷为滤镜名字符串）
    filter_changed = Signal(str)

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
            # 当某个按钮被勾选时发出 filter_changed 信号
            rb.toggled.connect(
                lambda checked, name=f: checked and self.filter_changed.emit(name)
            )
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
        self.batch_btn = QPushButton("Batch Import...")
        self.paste_btn = QPushButton("Paste (Ctrl+V)")
        btn_layout.addWidget(self.file_btn)
        btn_layout.addWidget(self.batch_btn)
        btn_layout.addWidget(self.paste_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # wire
        self.file_btn.clicked.connect(self.on_choose_file)
        self.batch_btn.clicked.connect(self.on_batch_import)
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

    def on_batch_import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select images",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not paths:
            return

        total = len(paths)
        progress = QProgressDialog("Importing snapshots...", "Cancel", 0, total, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setValue(0)

        imported = 0
        for idx, p in enumerate(paths, start=1):
            if progress.wasCanceled():
                break
            if self._handle_input_path(Path(p), confirm=False):
                imported += 1
            progress.setValue(idx)
            QApplication.processEvents()

        self.status_label.setText(f"Imported {imported} snapshots (batch)")

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

    def _handle_input_path(self, path: Path, *, confirm: bool = True) -> bool:
        self.status_label.setText("Processing...")
        ocr_date: Optional[str] = None
        predicted_date: Optional[str] = None
        detected_date: Optional[str] = None

        # OCR处理
        try:
            if self.ocr:
                # 直接使用manager需要的OCR参数格式
                raw_date = self.ocr.extract_date(
                    path,
                    roi_spec=None,  # 根据实际需要传递ROI参数
                    template_key=None,  # 根据OCR模板选择
                )
                ocr_date = raw_date or None
        except Exception:
            ocr_date = None

        # 后备逻辑：基于最后一个快照的日期预测
        last_date_iso = self._get_last_snapshot_date(self.current_filter())
        if last_date_iso:
            try:
                num = int(self.interval_spin.value())
                unit = self.interval_unit.currentText()
                predicted_date = self._add_interval_iso(last_date_iso, num, unit)
            except Exception:
                predicted_date = None

        # 默认优先 OCR，其次预测
        detected_date = ocr_date or predicted_date

        # 获取当前Campaign对象（关键修改点）
        try:
            campaign = self.storage.load_campaign(self.campaign_name)
        except FileNotFoundError:
            self.status_label.setText("Campaign not found")
            return

        # 交互导入：弹出确认对话框
        if confirm:
            filters = [f.value for f in FilterType]  # 使用核心枚举类型
            dlg = SnapshotConfirmDialog(
                self.window(),
                path,
                self.campaign_name,
                filters,
                detected_date_iso=detected_date,
            )

            # 将 OCR / 预测结果、当前滤镜传入对话框（若其支持）
            if hasattr(dlg, "set_candidates"):
                try:
                    dlg.set_candidates(ocr_date, predicted_date)
                except Exception:
                    pass
            # 尝试让对话框默认选中当前单选框滤镜
            try:
                current = self.current_filter()
                if hasattr(dlg, "filters") and hasattr(dlg, "filter_combo"):
                    if current in dlg.filters:
                        idx = dlg.filters.index(current)
                        dlg.filter_combo.setCurrentIndex(idx)
            except Exception:
                pass

            if dlg.exec() == QDialog.Accepted:
                data = dlg.get_result() or {}
                try:
                    # 兼容真实对话框与测试中的 Mock：字段名可能略有不同
                    filt_value = data.get("filter")
                    date_value = data.get("date") or data.get("date_iso")
                    if not filt_value or not date_value:
                        raise ValueError("Missing filter or date from dialog result")

                    # 使用storage/manager.py的接口规范
                    snap = self.storage.import_image(
                        campaign=campaign,
                        src_path=path,
                        filter_type=FilterType(filt_value),  # 转换为枚举类型
                        date_str=date_value,
                        ocr_provider=self.ocr,  # 传递OCR组件
                        create_dirs_if_missing=True,  # 确保目录创建
                    )

                    # 更新UI状态
                    self.status_label.setText(f"Imported snapshot {snap.date.to_iso()}")
                    # 通知上层界面：有新快照导入
                    try:
                        self.snapshot_added.emit(snap)
                    except Exception:
                        # 信号失败不应影响核心导入逻辑
                        pass
                    return True

                except ValueError as ve:  # 处理枚举/缺字段错误
                    self.status_label.setText(f"Invalid data: {str(ve)}")
                except Exception as e:
                    self.status_label.setText(f"Import failed: {e}")
            else:
                self.status_label.setText("Import cancelled")
            return False

        # 批量导入：不弹出对话框，直接使用当前单选框滤镜和自动/预测日期
        try:
            filt_value = self.current_filter()
            # 批量导入：优先使用 OCR 结果，其次预测，否则留给存储层回退
            snap = self.storage.import_image(
                campaign=campaign,
                src_path=path,
                filter_type=FilterType(filt_value),
                date_str=detected_date,
                ocr_provider=self.ocr,
                create_dirs_if_missing=True,
            )
            self.status_label.setText(f"Imported snapshot {snap.date.to_iso()}")
            try:
                self.snapshot_added.emit(snap)
            except Exception:
                pass
            return True
        except Exception as e:
            self.status_label.setText(f"Batch import failed: {e}")
            return False

    def _get_last_snapshot_date(self, filter_name: str) -> Optional[str]:
        meta = self.store.load_metadata(self.campaign_name) or {}
        snaps = meta.get("snapshots", [])
        dates = [
            s.get("date")
            for s in snaps
            if (s.get("filter_type") == filter_name or s.get("filter") == filter_name)
            and s.get("date")
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
