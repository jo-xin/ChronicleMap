from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.gui.campaign_detail import CampaignDetailWindow
from chroniclemap.gui.campaign_store import CampaignStore
from chroniclemap.gui.texts import get_locale, set_locale, tr


class NoteEditorDialog(QDialog):
    def __init__(self, parent: Optional[QWidget], initial_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.note_edit.title"))
        self.resize(600, 400)
        self.text = QTextEdit(self)
        self.text.setPlainText(initial_text)
        self.save_btn = QPushButton(tr("common.save"), self)
        self.cancel_btn = QPushButton(tr("common.cancel"), self)

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
        set_locale(self.store.get_global_language(default=get_locale()))
        self.setWindowTitle(tr("campaign_manager.title", app=tr("app.name")))
        self.resize(900, 600)
        self._detail_windows: list[CampaignDetailWindow] = []

        self.layout = QVBoxLayout(self)
        self.menu_bar = QMenuBar(self)
        self.layout.setMenuBar(self.menu_bar)
        self.settings_menu = self.menu_bar.addMenu("")
        self.language_menu = self.settings_menu.addMenu("")
        self.action_lang_en = QAction(self)
        self.action_lang_zh = QAction(self)
        self.language_menu.addAction(self.action_lang_en)
        self.language_menu.addAction(self.action_lang_zh)

        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton(tr("campaign_manager.new"))
        self.open_btn = QPushButton(tr("campaign_manager.open"))
        self.delete_btn = QPushButton(tr("campaign_manager.delete"))
        self.rename_btn = QPushButton(tr("campaign_manager.rename"))
        self.note_btn = QPushButton(tr("campaign_manager.edit_note"))
        btn_layout.addWidget(self.new_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.note_btn)
        self.layout.addLayout(btn_layout)

        self.status = QLabel("")
        self.layout.addWidget(self.status)

        self.new_btn.clicked.connect(self.on_new)
        self.delete_btn.clicked.connect(self.on_delete)
        self.rename_btn.clicked.connect(self.on_rename)
        self.note_btn.clicked.connect(self.on_edit_note)
        self.open_btn.clicked.connect(self.on_open)
        self.action_lang_en.triggered.connect(lambda: self._apply_language("en"))
        self.action_lang_zh.triggered.connect(lambda: self._apply_language("zh_CN"))

        self.retranslate_ui()
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
                self, tr("dlg.campaign_select.title"), tr("dlg.campaign_select.body")
            )
            return None
        return nm

    def on_new(self):
        name, ok = QInputDialog.getText(
            self, tr("dlg.new_campaign.title"), tr("dlg.new_campaign.name")
        )
        if not ok or not name.strip():
            return
        try:
            self.store.create_campaign(name.strip())
            self.status.setText(tr("status.campaign_created", name=name.strip()))
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def on_delete(self):
        nm = self.ensure_selection()
        if not nm:
            return
        reply = QMessageBox.question(
            self,
            tr("dlg.delete_campaign.title"),
            tr("dlg.delete_campaign.body", name=nm),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.store.delete_campaign(nm)
                self.status.setText(tr("status.campaign_deleted", name=nm))
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, tr("common.error"), str(e))

    def on_rename(self):
        nm = self.ensure_selection()
        if not nm:
            return
        new, ok = QInputDialog.getText(
            self,
            tr("dlg.rename_campaign.title"),
            tr("dlg.rename_campaign.name"),
            text=nm,
        )
        if not ok or not new.strip():
            return
        try:
            self.store.rename_campaign(nm, new.strip())
            self.status.setText(tr("status.campaign_renamed", old=nm, new=new.strip()))
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, tr("common.error"), str(e))

    def on_edit_note(self):
        nm = self.ensure_selection()
        if not nm:
            return
        meta = self.store.load_metadata(nm) or {}
        initial = meta.get("notes") or meta.get("note") or ""
        dlg = NoteEditorDialog(self, initial_text=initial)
        if dlg.exec() == QDialog.Accepted:
            txt = dlg.get_text()
            meta["notes"] = txt
            self.store.save_metadata(nm, meta)
            self.status.setText(tr("status.note_saved", name=nm))

    def on_open(self):
        nm = self.ensure_selection()
        if not nm:
            return
        detail = CampaignDetailWindow(nm, self.store)
        detail.show()
        self._detail_windows.append(detail)

        def _on_destroyed(_obj=None, win=detail):
            if win in self._detail_windows:
                self._detail_windows.remove(win)

        detail.destroyed.connect(_on_destroyed)

    def retranslate_ui(self):
        self.setWindowTitle(tr("campaign_manager.title", app=tr("app.name")))
        self.new_btn.setText(tr("campaign_manager.new"))
        self.open_btn.setText(tr("campaign_manager.open"))
        self.delete_btn.setText(tr("campaign_manager.delete"))
        self.rename_btn.setText(tr("campaign_manager.rename"))
        self.note_btn.setText(tr("campaign_manager.edit_note"))
        self.settings_menu.setTitle(tr("settings.menu"))
        self.language_menu.setTitle(tr("settings.language"))
        self.action_lang_en.setText(tr("settings.language.en"))
        self.action_lang_zh.setText(tr("settings.language.zh_CN"))

    def _apply_language(self, locale: str):
        resolved = set_locale(locale)
        self.store.set_global_language(resolved)
        self.retranslate_ui()
        for win in QApplication.topLevelWidgets():
            try:
                if hasattr(win, "retranslate_ui"):
                    win.retranslate_ui()
            except Exception:
                pass
        QMessageBox.information(
            self,
            tr("settings.language.applied_title"),
            tr("settings.language.applied_body"),
        )
