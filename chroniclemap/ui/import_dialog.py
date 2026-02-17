# chroniclemap/ui/import_dialog.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from chroniclemap.core.models import FilterType
from chroniclemap.services.storage_service import StorageService
from chroniclemap.ui.workers import ImportRunnable, OCRRunnable


def _add_months(dt: date, months: int) -> date:
    # naive month math: preserve day if possible, else clamp to month end
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = dt.day
    # clamp day
    import calendar

    mdays = calendar.monthrange(y, m)[1]
    if d > mdays:
        d = mdays
    return date(y, m, d)


def _add_years(dt: date, years: int) -> date:
    try:
        return date(dt.year + years, dt.month, dt.day)
    except ValueError:
        # e.g., Feb 29 -> Feb 28 fallback
        return date(dt.year + years, dt.month, 28)


class ImportDialog(QDialog):
    """
    Dialog to confirm import: shows preview, OCR detected date (editable), preview filename,
    and allows user to submit or cancel.
    """

    def __init__(
        self,
        storage_service: StorageService,
        campaign,
        image_path: Path,
        initial_filter: str | FilterType = FilterType.REALMS,
        default_interval: Tuple[int, str] = (365, "days"),
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Import Snapshot")
        self.resize(700, 420)
        self.storage = storage_service
        self.campaign = campaign
        self.image_path = Path(image_path)
        self.threadpool = QThreadPool.globalInstance()

        # UI elements
        layout = QHBoxLayout(self)

        # left: image preview
        left = QVBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(360, 200)
        left.addWidget(self.preview_label)
        left.addStretch(1)
        layout.addLayout(left, 1)

        # right: controls
        right = QVBoxLayout()

        # filter display (read-only here; main window has radio control)
        self.filter_label = QLabel(f"Filter: {initial_filter}")
        right.addWidget(self.filter_label)

        # detected/selected date (editable)
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        right.addWidget(QLabel("Detected / Selected date (editable):"))
        right.addWidget(self.date_edit)

        # preview filename
        self.filename_preview = QLabel("Filename preview: -")
        right.addWidget(self.filename_preview)

        # actions
        btn_layout = QHBoxLayout()
        self.submit_btn = QPushButton("Submit (Save)")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.cancel_btn)
        right.addLayout(btn_layout)

        layout.addLayout(right, 1)

        # wire
        self.submit_btn.clicked.connect(self._on_submit)
        self.cancel_btn.clicked.connect(self.reject)

        # initial
        self._set_preview_pixmap(self.image_path)
        self.filter_value = (
            initial_filter if isinstance(initial_filter, str) else initial_filter.value
        )
        # run OCR in background to fill date_edit if possible
        self.date_edit.setText("")  # blank until OCR
        self._start_ocr_and_suggest_date(default_interval)

    def _set_preview_pixmap(self, path: Path):
        pix = QPixmap(str(path))
        if pix.isNull():
            self.preview_label.setText("Preview not available")
            return
        scaled = pix.scaled(
            self.preview_label.width(),
            self.preview_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _start_ocr_and_suggest_date(self, default_interval: Tuple[int, str]):
        """
        Try OCR first; if OCR yields date, set it. Otherwise compute suggestion based on last snapshot + default_interval.
        default_interval: (value, unit) where unit in {"days", "months", "years"}
        """
        # start OCR runnable
        runnable = OCRRunnable(self.image_path)
        runnable.signals.result.connect(self._on_ocr_result)
        runnable.signals.error.connect(self._on_ocr_error)
        runnable.signals.finished.connect(lambda: None)
        self.threadpool.start(runnable)
        # meanwhile compute suggestion and set as fallback (will be overwritten by OCR if success)
        suggested = self._compute_suggested_date(default_interval)
        if suggested:
            self.date_edit.setText(suggested.isoformat())
            self._update_filename_preview(suggested)

    def _on_ocr_result(self, date_str: Optional[str]):
        if date_str:
            # normalize to YYYY-MM-DD (OCR provider ensures format like that)
            try:
                d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
                self.date_edit.setText(d.isoformat())
                self._update_filename_preview(d)
                return
            except Exception:
                # if parsing fails, ignore
                pass
        # else leave existing suggestion

    def _on_ocr_error(self, err):
        # ignore OCR errors but could show message
        pass

    def _compute_suggested_date(
        self, default_interval: Tuple[int, str]
    ) -> Optional[date]:
        """
        Find last snapshot in this campaign for `self.filter_value` and add interval.
        If none found, use today's date.
        """
        try:
            snaps = [
                s
                for s in self.campaign.snapshots
                if (
                    s.filter_type == self.filter_value
                    or getattr(s.filter_type, "value", None) == self.filter_value
                    or str(s.filter_type) == self.filter_value
                )
            ]
            if snaps:
                # find latest date
                last = max(snaps, key=lambda s: s.date).date
            else:
                last = date.today()
            val, unit = default_interval
            if unit == "days":
                return last + timedelta(days=val)
            elif unit == "months":
                return _add_months(last, val)
            elif unit == "years":
                return _add_years(last, val)
        except Exception:
            return date.today()
        return date.today()

    def _update_filename_preview(self, d: date):
        # campaign.path / maps / <filter> / YYYY-MM-DD.png
        maps_dir = Path(self.campaign.path) / "maps"
        filt = str(self.filter_value)
        preview_path = maps_dir / filt / f"{d.isoformat()}.png"
        self.filename_preview.setText(f"Filename preview: {preview_path}")

    def _on_submit(self):
        txt = self.date_edit.text().strip()
        try:
            dt = datetime.strptime(txt, "%Y-%m-%d").date()
        except Exception:
            QMessageBox.warning(
                self, "Invalid date", "Please enter date in YYYY-MM-DD format."
            )
            return
        # start ImportRunnable in background using given date & filter
        self.submit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        runnable = ImportRunnable(
            storage_service=self.storage,
            campaign=self.campaign,
            src_path=self.image_path,
            filter_name=self.filter_value,
            date_str=dt.isoformat(),
        )
        # connect result to close dialog on success
        runnable.signals.result.connect(lambda snap: self.accept())
        runnable.signals.error.connect(
            lambda err: QMessageBox.critical(self, "Import Error", f"{err}")
        )
        runnable.signals.finished.connect(lambda: None)
        self.threadpool.start(runnable)
