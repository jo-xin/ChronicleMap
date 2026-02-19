# chroniclemap/gui/campaign_manager.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.gui.campaign_store import CampaignStore  # use the adapter above


class NoteEditorDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], initial_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Edit Note")
        self.resize(600, 400)
        self.text = QTextEdit(self)
        self.text.setPlainText(initial_text)
        self.save_btn = QPushButton("Save", self)
        self.cancel_btn = QPushButton("Cancel", self)

        layout = QVBoxLayout()
        layout.addWidget(self.text)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_text(self) -> str:
        return self.text.toPlainText()


class CampaignManagerView(QWidget):
    def __init__(self, store: CampaignStore):
        super().__init__()
        self.store = store
        self.setWindowTitle("ChronicleMap — Campaign Manager")
        self.resize(900, 600)

        self.layout = QVBoxLayout(self)

        # list
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

        # buttons
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.open_btn = QPushButton("Open")
        self.delete_btn = QPushButton("Delete")
        self.rename_btn = QPushButton("Rename")
        self.note_btn = QPushButton("Edit Note")
        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.note_btn)
        self.layout.addLayout(btn_layout)

        # status
        self.status = QLabel("")
        self.layout.addWidget(self.status)

        # wire up
        self.new_btn.clicked.connect(self.on_new)
        self.delete_btn.clicked.connect(self.on_delete)
        self.rename_btn.clicked.connect(self.on_rename)
        self.note_btn.clicked.connect(self.on_edit_note)
        self.open_btn.clicked.connect(self.on_open)

        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.store.list_campaigns():
            name = entry["name"]
            meta = entry.get("metadata") or {}
            created = meta.get("created_at") or meta.get("created") or ""
            item = QtWidgets.QListWidgetItem(
                f"{name}    ({created[:10] if created else ''})"
            )
            item.setData(QtCore.Qt.UserRole, name)
            self.list_widget.addItem(item)

    def selected_name(self) -> Optional[str]:
        it = self.list_widget.currentItem()
        if not it:
            return None
        return it.data(QtCore.Qt.UserRole)

    def ensure_selection(self) -> Optional[str]:
        nm = self.selected_name()
        if not nm:
            QMessageBox.information(
                self, "Select Campaign", "Please select a campaign first."
            )
            return None
        return nm

    def on_new(self):
        name, ok = QInputDialog.getText(self, "New Campaign", "Campaign name:")
        if not ok or not name.strip():
            return
        try:
            _camp = self.store.create_campaign(name.strip())
            self.status.setText(f"Created campaign '{name.strip()}'")
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_delete(self):
        nm = self.ensure_selection()
        if not nm:
            return
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete campaign '{nm}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.store.delete_campaign(nm)
                self.status.setText(f"Deleted campaign '{nm}'")
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def on_rename(self):
        nm = self.ensure_selection()
        if not nm:
            return
        new, ok = QInputDialog.getText(self, "Rename Campaign", "New name:", text=nm)
        if not ok or not new.strip():
            return
        try:
            self.store.rename_campaign(nm, new.strip())
            self.status.setText(f"Renamed '{nm}' -> '{new.strip()}'")
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_edit_note(self):
        nm = self.ensure_selection()
        if not nm:
            return
        meta = self.store.load_metadata(nm) or {}
        initial = meta.get("notes") or meta.get("note") or ""
        dlg = NoteEditorDialog(self, initial_text=initial)
        if dlg.exec() == QDialog.Accepted:
            txt = dlg.get_text()
            # save under 'notes' key to be compatible with Campaign.to_dict
            meta["notes"] = txt
            self.store.save_metadata(nm, meta)
            self.status.setText(f"Saved note for '{nm}'")

    def on_open(self):
        nm = self.ensure_selection()
        if not nm:
            return
        QMessageBox.information(self, "Open", f"Would open campaign: {nm}")
