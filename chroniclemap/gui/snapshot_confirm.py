# chroniclemap/gui/snapshot_confirm.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 使用项目中的 GameDate 与 FilterType
from chroniclemap.core.models import FilterType, GameDate


class SnapshotConfirmDialog(QDialog):
    """
    Confirm dialog that uses GameDate for date parsing/validation instead of QDateEdit.
    Input: detected_date_iso (optional) - a string like '1450-06-01' or None
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        src_path: Path,
        campaign_name: str,
        filters: List[str],
        detected_date_iso: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Confirm Snapshot")
        self.resize(700, 420)
        self.src_path = Path(src_path)
        self.campaign_name = campaign_name
        # Normalize filters to strings (prefer FilterType values if given)
        norm_filters = []
        for f in filters:
            if isinstance(f, FilterType):
                norm_filters.append(f.value)
            else:
                norm_filters.append(str(f))
        self.filters = norm_filters
        self.result_data = None  # will hold dict on accept
        # 这两个字段会在 set_candidates 中被设置
        self.ocr_candidate: Optional[str] = None
        self.predicted_candidate: Optional[str] = None

        layout = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()

        # left: image preview
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pix = QPixmap(str(self.src_path))
        if not pix.isNull():
            pix = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(pix)
        else:
            self.preview_label.setText("Preview not available")
        left.addWidget(self.preview_label)

        # right: inputs
        right.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.filters)
        right.addWidget(self.filter_combo)

        # OCR / 预测结果展示区
        right.addWidget(QLabel("Detected dates:"))
        self.ocr_label = QLabel("OCR: (none)")
        self.pred_label = QLabel("Predicted: (none)")
        right.addWidget(self.ocr_label)
        right.addWidget(self.pred_label)

        # 快速应用按钮
        self.use_ocr_btn = QPushButton("Use OCR result")
        self.use_pred_btn = QPushButton("Use predicted result")
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(self.use_ocr_btn)
        quick_layout.addWidget(self.use_pred_btn)
        right.addLayout(quick_layout)

        right.addWidget(QLabel("Date (ISO, e.g. 1450-06-01):"))
        # Use plain text input; validate with GameDate.fromiso
        self.date_input = QLineEdit()
        if detected_date_iso:
            self.date_input.setText(detected_date_iso)
        right.addWidget(self.date_input)

        # validation label
        self.validation_label = QLabel()
        right.addWidget(self.validation_label)

        right.addWidget(QLabel("Filename preview:"))
        self.filename_preview = QLineEdit()
        self.filename_preview.setReadOnly(True)
        right.addWidget(self.filename_preview)

        right.addWidget(QLabel("Note (optional):"))
        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(80)
        right.addWidget(self.note_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        right.addLayout(btn_layout)

        layout.addLayout(left, 1)
        layout.addLayout(right, 1)
        self.setLayout(layout)

        # wire up
        self.filter_combo.currentTextChanged.connect(self._update_filename_preview)
        self.date_input.textChanged.connect(self._on_date_changed)
        self._on_date_changed()
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)
        self.use_ocr_btn.clicked.connect(self._apply_ocr_candidate)
        self.use_pred_btn.clicked.connect(self._apply_predicted_candidate)

    def _on_date_changed(self):
        txt = self.date_input.text().strip()
        if not txt:
            self._set_invalid("Date empty")
            return
        try:
            gd = GameDate.fromiso(txt)
            iso = gd.to_iso()
            self._set_valid(f"Parsed as {iso}")
            self._update_filename_preview_from_iso(iso)
        except Exception as e:
            # invalid date
            self._set_invalid(f"Invalid date: {e}")
            # still update preview conservatively
            self._update_filename_preview_from_iso(None)

    def _set_valid(self, msg: str):
        self.validation_label.setText(f"✓ {msg}")
        self.validation_label.setStyleSheet("color: green;")

    def _set_invalid(self, msg: str):
        self.validation_label.setText(f"✗ {msg}")
        self.validation_label.setStyleSheet("color: red;")

    def _update_filename_preview(self):
        # called when filter changes; uses current date input's parsed iso if valid
        txt = self.date_input.text().strip()
        try:
            gd = GameDate.fromiso(txt)
            iso = gd.to_iso()
        except Exception:
            iso = None
        self._update_filename_preview_from_iso(iso)

    def _update_filename_preview_from_iso(self, iso: Optional[str]):
        filt = self.filter_combo.currentText()
        ext = self.src_path.suffix or ".png"
        if iso:
            self.filename_preview.setText(f"maps/{filt}/{iso}{ext}")
        else:
            self.filename_preview.setText(f"maps/{filt}/<invalid-date>{ext}")

    # -------------------
    # Candidate helpers
    # -------------------

    def set_candidates(
        self, ocr_date: Optional[str], predicted_date: Optional[str]
    ) -> None:
        """由调用方设置 OCR / 预测得到的日期，并刷新 UI。"""
        self.ocr_candidate = ocr_date
        self.predicted_candidate = predicted_date

        if ocr_date:
            self.ocr_label.setText(f"OCR: {ocr_date}")
        else:
            self.ocr_label.setText("OCR: (none)")

        if predicted_date:
            self.pred_label.setText(f"Predicted: {predicted_date}")
        else:
            self.pred_label.setText("Predicted: (none)")

        # 默认优先使用 OCR 结果填入输入框
        if ocr_date:
            self.date_input.setText(ocr_date)
        elif predicted_date and not self.date_input.text().strip():
            self.date_input.setText(predicted_date)

        # 同步一次文件名预览
        self._on_date_changed()

    def _apply_ocr_candidate(self) -> None:
        if self.ocr_candidate:
            self.date_input.setText(self.ocr_candidate)

    def _apply_predicted_candidate(self) -> None:
        if self.predicted_candidate:
            self.date_input.setText(self.predicted_candidate)

    def on_save(self):
        txt = self.date_input.text().strip()
        try:
            gd = GameDate.fromiso(txt)
            iso = gd.to_iso()
        except Exception as e:
            # Guard: shouldn't happen if UI prevents it, but be safe
            self._set_invalid(f"Invalid date: {e}")
            return
        self.result_data = {
            "campaign": self.campaign_name,
            "filter": self.filter_combo.currentText(),
            # 同时提供 date 与 date_iso，方便不同调用方/旧代码复用
            "date": iso,
            "date_iso": iso,
            "note": self.note_edit.toPlainText(),
            "src_path": str(self.src_path),
        }
        self.accept()

    def get_result(self):
        return self.result_data
