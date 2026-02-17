# chroniclemap/ui/campaign_manager.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from chroniclemap.ui.viewmodels import AppViewModel


class CampaignManagerDialog(QDialog):
    """
    Dialog showing list of campaigns and basic actions:
    Create, Delete, Open.
    Emits signal via AppViewModel when open requested.
    """

    def __init__(self, app_vm: AppViewModel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Campaigns")
        self.resize(600, 400)
        self.app_vm = app_vm

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # buttons
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.open_btn = QPushButton("Open")
        self.delete_btn = QPushButton("Delete")
        self.refresh_btn = QPushButton("Refresh")
        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.refresh_btn)
        layout.addLayout(btn_layout)

        # info
        self.info_label = QLabel("Select a campaign to open or edit.")
        layout.addWidget(self.info_label)

        # wire
        self.new_btn.clicked.connect(self.on_new)
        self.open_btn.clicked.connect(self.on_open)
        self.delete_btn.clicked.connect(self.on_delete)
        self.refresh_btn.clicked.connect(self.on_refresh)

        # subscribe to app_vm
        self.app_vm.campaigns_changed.connect(self.on_campaigns_changed)
        self.app_vm.refresh_campaigns()

    def on_campaigns_changed(self, names):
        self.list_widget.clear()
        for n in names:
            self.list_widget.addItem(n)

    def selected_name(self) -> str | None:
        it = self.list_widget.currentItem()
        return it.text() if it else None

    def on_new(self):
        name, ok = QInputDialog.getText(self, "New campaign", "Campaign name:")
        if not ok or not name:
            return
        try:
            self.app_vm.create_campaign(name)
            QMessageBox.information(
                self, "Created", f"Campaign '{name}' created and opened."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_open(self):
        name = self.selected_name()
        if not name:
            QMessageBox.warning(self, "No selection", "Please select a campaign.")
            return
        self.app_vm.open_campaign_by_name(name)
        self.accept()

    def on_delete(self):
        name = self.selected_name()
        if not name:
            QMessageBox.warning(self, "No selection", "Please select a campaign.")
            return
        confirm = QMessageBox.question(
            self, "Delete", f"Delete campaign '{name}'? This cannot be undone."
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.app_vm.delete_campaign(name)
            QMessageBox.information(self, "Deleted", f"Campaign '{name}' deleted.")
            self.app_vm.refresh_campaigns()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_refresh(self):
        self.app_vm.refresh_campaigns()
