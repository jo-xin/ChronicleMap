from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.gui.campaign_store import CampaignStore
from chroniclemap.gui.import_widget import ImportWidget
from chroniclemap.gui.player_window import PlayerWindow
from chroniclemap.gui.texts import tr
from chroniclemap.storage.manager import StorageManager
from chroniclemap.vision.ocr import TesseractOCRProvider


class CampaignDetailWindow(QWidget):
    def __init__(
        self,
        campaign_name: str,
        store: CampaignStore,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.store = store
        self.storage = StorageManager(self.store.root)
        self.ocr = TesseractOCRProvider()

        self.setWindowTitle(
            tr("campaign_detail.title", app=tr("app.name"), campaign=campaign_name)
        )
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        self.info_label = QLabel(tr("campaign_detail.info", campaign=campaign_name))
        layout.addWidget(self.info_label)

        top_layout = QHBoxLayout()
        layout.addLayout(top_layout, 1)

        self.snapshot_list = QListWidget()
        self.snapshot_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        top_layout.addWidget(self.snapshot_list, 2)

        right_panel = QVBoxLayout()
        top_layout.addLayout(right_panel, 3)

        self.preview_group = QGroupBox(tr("campaign_detail.preview"))
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel(tr("campaign_detail.no_snapshot"))
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        preview_layout.addWidget(self.preview_label)
        open_btns = QHBoxLayout()
        self.open_folder_btn = QPushButton(tr("campaign_detail.open_folder"))
        self.open_external_btn = QPushButton(tr("campaign_detail.open_external"))
        open_btns.addWidget(self.open_folder_btn)
        open_btns.addWidget(self.open_external_btn)
        preview_layout.addLayout(open_btns)
        self.preview_group.setLayout(preview_layout)
        right_panel.addWidget(self.preview_group)

        self.single_group = QGroupBox(tr("campaign_detail.edit_selected"))
        single_form = QFormLayout()
        self.single_date_edit = QLineEdit()
        self.single_filter_combo = QComboBox()
        self.single_filter_combo.addItems([f.value for f in FilterType])
        self.single_apply_btn = QPushButton(tr("campaign_detail.apply_single"))
        self.single_date_label = QLabel(tr("campaign_detail.date_label"))
        self.single_filter_label = QLabel(tr("common.filter"))
        single_form.addRow(self.single_date_label, self.single_date_edit)
        single_form.addRow(self.single_filter_label, self.single_filter_combo)
        single_form.addRow(self.single_apply_btn)
        self.single_group.setLayout(single_form)
        right_panel.addWidget(self.single_group)

        self.bulk_group = QGroupBox(tr("campaign_detail.bulk_edit"))
        bulk_layout = QVBoxLayout()
        bulk_filter_row = QHBoxLayout()
        self.bulk_filter_combo = QComboBox()
        self.bulk_filter_combo.addItems([f.value for f in FilterType])
        self.bulk_filter_btn = QPushButton(tr("campaign_detail.bulk_set_filter"))
        bulk_filter_row.addWidget(self.bulk_filter_combo)
        bulk_filter_row.addWidget(self.bulk_filter_btn)
        bulk_layout.addLayout(bulk_filter_row)

        bulk_date_row = QHBoxLayout()
        self.bulk_sign_combo = QComboBox()
        self.bulk_sign_combo.addItems(["+", "-"])
        self.bulk_delta_spin = QSpinBox()
        self.bulk_delta_spin.setMinimum(1)
        self.bulk_delta_spin.setMaximum(100000)
        self.bulk_unit_combo = QComboBox()
        self.bulk_unit_combo.addItem(tr("unit.days"), "days")
        self.bulk_unit_combo.addItem(tr("unit.years"), "years")
        self.bulk_date_btn = QPushButton(tr("campaign_detail.bulk_apply_date"))
        bulk_date_row.addWidget(self.bulk_sign_combo)
        bulk_date_row.addWidget(self.bulk_delta_spin)
        bulk_date_row.addWidget(self.bulk_unit_combo)
        bulk_date_row.addWidget(self.bulk_date_btn)
        bulk_layout.addLayout(bulk_date_row)

        self.bulk_delete_btn = QPushButton(tr("campaign_detail.bulk_delete"))
        bulk_layout.addWidget(self.bulk_delete_btn)
        self.bulk_group.setLayout(bulk_layout)
        right_panel.addWidget(self.bulk_group)

        self.import_widget = ImportWidget(
            campaign_name=campaign_name,
            campaign_store=self.store,
            storage_manager=self.storage,
            ocr_provider=self.ocr,
            parent=self,
        )
        layout.addWidget(self.import_widget, 0)

        bottom = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("campaign_detail.refresh"))
        self.open_player_btn = QPushButton(tr("campaign_detail.open_player"))
        self.close_btn = QPushButton(tr("common.close"))
        bottom.addWidget(self.refresh_btn)
        bottom.addWidget(self.open_player_btn)
        bottom.addStretch()
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

        self.refresh_btn.clicked.connect(self.refresh_snapshots)
        self.open_player_btn.clicked.connect(self._open_player)
        self.close_btn.clicked.connect(self.close)
        self.snapshot_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.open_folder_btn.clicked.connect(self._open_selected_folder)
        self.open_external_btn.clicked.connect(self._open_selected_external)
        self.single_apply_btn.clicked.connect(self._apply_single_edit)
        self.bulk_filter_btn.clicked.connect(self._apply_bulk_filter)
        self.bulk_date_btn.clicked.connect(self._apply_bulk_date_offset)
        self.bulk_delete_btn.clicked.connect(self._delete_selected_snapshots)

        if hasattr(self.import_widget, "snapshot_added"):
            self.import_widget.snapshot_added.connect(
                lambda _snap: self.refresh_snapshots()
            )
        if hasattr(self.import_widget, "filter_changed"):
            self.import_widget.filter_changed.connect(
                lambda _name: self.refresh_snapshots()
            )

        self.refresh_snapshots()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(
            tr("campaign_detail.title", app=tr("app.name"), campaign=self.campaign_name)
        )
        self.info_label.setText(tr("campaign_detail.info", campaign=self.campaign_name))
        self.preview_group.setTitle(tr("campaign_detail.preview"))
        if not self._selected_snapshot_dicts():
            self.preview_label.setText(tr("campaign_detail.no_snapshot"))
        self.open_folder_btn.setText(tr("campaign_detail.open_folder"))
        self.open_external_btn.setText(tr("campaign_detail.open_external"))
        self.single_group.setTitle(tr("campaign_detail.edit_selected"))
        self.single_apply_btn.setText(tr("campaign_detail.apply_single"))
        self.single_date_label.setText(tr("campaign_detail.date_label"))
        self.single_filter_label.setText(tr("common.filter"))
        self.bulk_group.setTitle(tr("campaign_detail.bulk_edit"))
        cur_unit = self.bulk_unit_combo.currentData() or "days"
        self.bulk_unit_combo.setItemText(0, tr("unit.days"))
        self.bulk_unit_combo.setItemText(1, tr("unit.years"))
        idx = self.bulk_unit_combo.findData(cur_unit)
        if idx >= 0:
            self.bulk_unit_combo.setCurrentIndex(idx)
        self.bulk_filter_btn.setText(tr("campaign_detail.bulk_set_filter"))
        self.bulk_date_btn.setText(tr("campaign_detail.bulk_apply_date"))
        self.bulk_delete_btn.setText(tr("campaign_detail.bulk_delete"))
        self.refresh_btn.setText(tr("campaign_detail.refresh"))
        self.open_player_btn.setText(tr("campaign_detail.open_player"))
        self.close_btn.setText(tr("common.close"))
        if hasattr(self.import_widget, "retranslate_ui"):
            self.import_widget.retranslate_ui()

    def refresh_snapshots(self) -> None:
        self.snapshot_list.clear()
        try:
            meta = self.store.load_metadata(self.campaign_name) or {}
        except FileNotFoundError:
            return

        snaps = meta.get("snapshots", [])
        current_filter: Optional[str] = None
        try:
            if hasattr(self.import_widget, "current_filter"):
                current_filter = self.import_widget.current_filter()
        except Exception:
            current_filter = None

        for s in snaps:
            date = s.get("date") or ""
            filter_type = s.get("filter_type") or s.get("filter") or ""
            if current_filter and filter_type and filter_type != current_filter:
                continue
            path = s.get("path") or ""
            text = f"{date} [{filter_type}] | {os.path.basename(path)}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s)
            self.snapshot_list.addItem(item)

    def _selected_snapshot_dicts(self) -> List[dict]:
        result: List[dict] = []
        for it in self.snapshot_list.selectedItems():
            data = it.data(Qt.UserRole)
            if isinstance(data, dict):
                result.append(data)
        return result

    def _load_campaign(self):
        return self.storage.load_campaign(self.campaign_name)

    def _on_selection_changed(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            self.preview_label.setText(tr("campaign_detail.no_snapshot"))
            self.single_date_edit.clear()
            return
        first = selected[0]
        path = first.get("path") or ""
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pix)
            else:
                self.preview_label.setText(tr("common.preview_na"))
        else:
            self.preview_label.setText(tr("common.preview_na"))

        self.single_date_edit.setText(first.get("date") or "")
        filt = first.get("filter_type") or first.get("filter") or ""
        if filt and filt in [f.value for f in FilterType]:
            self.single_filter_combo.setCurrentIndex(
                [f.value for f in FilterType].index(filt)
            )

    def _open_selected_folder(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        path = selected[0].get("path")
        if not path:
            return
        folder_path = os.path.dirname(path)
        if os.path.exists(folder_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    def _open_selected_external(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        path = selected[0].get("path")
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _apply_single_edit(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        snap_id = selected[0].get("id")
        if not snap_id:
            return
        try:
            gd = GameDate.fromiso(self.single_date_edit.text().strip())
        except Exception:
            return
        try:
            filt = FilterType(self.single_filter_combo.currentText())
        except Exception:
            filt = FilterType.CUSTOM

        camp = self._load_campaign()
        snap = self.storage.find_snapshot_by_id(camp, snap_id)
        if not snap:
            return
        snap.date = gd
        snap.filter_type = filt
        camp.snapshots.sort(key=lambda s: s.date.to_ordinal(False))
        self.storage.save_campaign(camp)
        self.refresh_snapshots()

    def _open_player(self) -> None:
        base_root = self.storage.base_dir.parent
        player = PlayerWindow(
            self.campaign_name, storage_base_dir=base_root, parent=None
        )
        player.show()

    def _apply_bulk_filter(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        try:
            filt = FilterType(self.bulk_filter_combo.currentText())
        except Exception:
            filt = FilterType.CUSTOM
        camp = self._load_campaign()
        selected_ids = {s.get("id") for s in selected if s.get("id")}
        for snap in camp.snapshots:
            if snap.id in selected_ids:
                snap.filter_type = filt
        self.storage.save_campaign(camp)
        self.refresh_snapshots()

    def _apply_bulk_date_offset(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        sign = 1 if self.bulk_sign_combo.currentText() == "+" else -1
        delta = self.bulk_delta_spin.value() * sign
        unit = self.bulk_unit_combo.currentData() or self.bulk_unit_combo.currentText()
        camp = self._load_campaign()
        id_set = {s.get("id") for s in selected if s.get("id")}
        for snap in camp.snapshots:
            if snap.id not in id_set:
                continue
            if unit == "days":
                snap.date = snap.date.add_days(delta)
            else:
                new_year = snap.date.year + delta
                try:
                    snap.date = GameDate(new_year, snap.date.month, snap.date.day)
                except Exception:
                    import calendar

                    mdays = calendar.monthrange(new_year, snap.date.month)[1]
                    snap.date = GameDate(new_year, snap.date.month, mdays)
        camp.snapshots.sort(key=lambda s: s.date.to_ordinal(False))
        self.storage.save_campaign(camp)
        self.refresh_snapshots()

    def _delete_selected_snapshots(self) -> None:
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        reply = QMessageBox.question(
            self,
            tr("campaign_detail.delete_title"),
            tr("campaign_detail.delete_body", count=len(selected)),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        camp = self._load_campaign()
        ids = [s.get("id") for s in selected if s.get("id")]
        self.storage.delete_snapshots(camp, ids, delete_files=True)
        self.refresh_snapshots()
