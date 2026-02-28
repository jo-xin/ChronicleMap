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

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.gui.texts import tr


class SnapshotConfirmDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget],
        src_path: Path,
        campaign_name: str,
        filters: List[str],
        detected_date_iso: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("snapshot_confirm.title"))
        self.resize(700, 420)
        self.src_path = Path(src_path)
        self.campaign_name = campaign_name
        self.filters = [
            f.value if isinstance(f, FilterType) else str(f) for f in filters
        ]
        self.result_data = None
        self.ocr_candidate: Optional[str] = None
        self.predicted_candidate: Optional[str] = None

        layout = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pix = QPixmap(str(self.src_path))
        if not pix.isNull():
            pix = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(pix)
        else:
            self.preview_label.setText(tr("snapshot_confirm.preview_na"))
        left.addWidget(self.preview_label)

        right.addWidget(QLabel(tr("snapshot_confirm.filter")))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.filters)
        right.addWidget(self.filter_combo)

        right.addWidget(QLabel(tr("snapshot_confirm.detected_dates")))
        self.ocr_label = QLabel(tr("snapshot_confirm.ocr_none"))
        self.pred_label = QLabel(tr("snapshot_confirm.pred_none"))
        right.addWidget(self.ocr_label)
        right.addWidget(self.pred_label)

        self.use_ocr_btn = QPushButton(tr("snapshot_confirm.use_ocr"))
        self.use_pred_btn = QPushButton(tr("snapshot_confirm.use_pred"))
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(self.use_ocr_btn)
        quick_layout.addWidget(self.use_pred_btn)
        right.addLayout(quick_layout)

        right.addWidget(QLabel(tr("snapshot_confirm.date_label")))
        self.date_input = QLineEdit()
        if detected_date_iso:
            self.date_input.setText(detected_date_iso)
        right.addWidget(self.date_input)

        self.validation_label = QLabel()
        right.addWidget(self.validation_label)

        right.addWidget(QLabel(tr("snapshot_confirm.filename_preview")))
        self.filename_preview = QLineEdit()
        self.filename_preview.setReadOnly(True)
        right.addWidget(self.filename_preview)

        right.addWidget(QLabel(tr("snapshot_confirm.note")))
        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(80)
        right.addWidget(self.note_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton(tr("snapshot_confirm.cancel"))
        self.save_btn = QPushButton(tr("snapshot_confirm.save"))
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        right.addLayout(btn_layout)

        layout.addLayout(left, 1)
        layout.addLayout(right, 1)
        self.setLayout(layout)

        self.filter_combo.currentTextChanged.connect(self._update_filename_preview)
        self.date_input.textChanged.connect(self._on_date_changed)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)
        self.use_ocr_btn.clicked.connect(self._apply_ocr_candidate)
        self.use_pred_btn.clicked.connect(self._apply_predicted_candidate)
        self._on_date_changed()

    def _on_date_changed(self):
        txt = self.date_input.text().strip()
        if not txt:
            self._set_invalid(tr("snapshot_confirm.date_empty"))
            return
        try:
            gd = GameDate.fromiso(txt)
            iso = gd.to_iso()
            self._set_valid(tr("snapshot_confirm.parsed_as", iso=iso))
            self._update_filename_preview_from_iso(iso)
        except Exception as e:
            self._set_invalid(tr("snapshot_confirm.invalid_date", err=str(e)))
            self._update_filename_preview_from_iso(None)

    def _set_valid(self, msg: str):
        self.validation_label.setText(msg)
        self.validation_label.setStyleSheet("color: green;")

    def _set_invalid(self, msg: str):
        self.validation_label.setText(msg)
        self.validation_label.setStyleSheet("color: red;")

    def _update_filename_preview(self):
        txt = self.date_input.text().strip()
        try:
            iso = GameDate.fromiso(txt).to_iso()
        except Exception:
            iso = None
        self._update_filename_preview_from_iso(iso)

    def _update_filename_preview_from_iso(self, iso: Optional[str]):
        filt = self.filter_combo.currentText()
        ext = self.src_path.suffix or ".png"
        if iso:
            self.filename_preview.setText(f"maps/{filt}/{iso}{ext}")
        else:
            self.filename_preview.setText(
                f"maps/{filt}/{tr('snapshot_confirm.invalid_date_tag')}{ext}"
            )

    def set_candidates(
        self, ocr_date: Optional[str], predicted_date: Optional[str]
    ) -> None:
        self.ocr_candidate = ocr_date
        self.predicted_candidate = predicted_date
        self.ocr_label.setText(
            tr("snapshot_confirm.ocr_value", date=ocr_date)
            if ocr_date
            else tr("snapshot_confirm.ocr_none")
        )
        self.pred_label.setText(
            tr("snapshot_confirm.pred_value", date=predicted_date)
            if predicted_date
            else tr("snapshot_confirm.pred_none")
        )
        if ocr_date:
            self.date_input.setText(ocr_date)
        elif predicted_date and not self.date_input.text().strip():
            self.date_input.setText(predicted_date)
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
            iso = GameDate.fromiso(txt).to_iso()
        except Exception as e:
            self._set_invalid(tr("snapshot_confirm.invalid_date", err=str(e)))
            return
        self.result_data = {
            "campaign": self.campaign_name,
            "filter": self.filter_combo.currentText(),
            "date": iso,
            "date_iso": iso,
            "note": self.note_edit.toPlainText(),
            "src_path": str(self.src_path),
        }
        self.accept()

    def get_result(self):
        return self.result_data
