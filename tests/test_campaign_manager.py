# tests/test_campaign_manager.py
import json

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from chroniclemap.gui.campaign_manager import CampaignManagerView
from chroniclemap.gui.campaign_store import CampaignStore


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    # create temporary directory and ensure it's used as home-like root
    root = tmp_path / "data"
    root.mkdir()
    return root


@pytest.fixture
def store(tmp_data_dir):
    return CampaignStore(tmp_data_dir)


@pytest.fixture
def manager_widget(qtbot, store):
    w = CampaignManagerView(store)
    qtbot.addWidget(w)
    w.show()
    return w


def test_create_campaign_via_gui(monkeypatch, qtbot, manager_widget, tmp_data_dir):
    # monkeypatch QInputDialog.getText to simulate user input
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("TestCampaign", True))
    qtbot.mouseClick(manager_widget.new_btn, Qt.LeftButton)
    qtbot.wait(100)
    # list should contain TestCampaign
    items = [
        manager_widget.list_widget.item(i).data(Qt.UserRole)
        for i in range(manager_widget.list_widget.count())
    ]
    assert "TestCampaign" in items
    # metadata file exists
    meta_file = tmp_data_dir / "Campaigns" / "TestCampaign" / "metadata.json"
    assert meta_file.exists()
    with meta_file.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["name"] == "TestCampaign"


def test_delete_campaign_via_gui(
    monkeypatch, qtbot, manager_widget, store, tmp_data_dir
):
    # create campaign directly
    store.create_campaign("ToDelete")
    manager_widget.refresh_list()
    # select the item
    for i in range(manager_widget.list_widget.count()):
        it = manager_widget.list_widget.item(i)
        if it.data(Qt.UserRole) == "ToDelete":
            manager_widget.list_widget.setCurrentRow(i)
            break
    # monkeypatch confirmation dialog to auto-Yes
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    qtbot.mouseClick(manager_widget.delete_btn, Qt.LeftButton)
    qtbot.wait(100)
    # folder should be removed
    assert not (tmp_data_dir / "Campaigns" / "ToDelete").exists()


def test_edit_note_saves_metadata(
    monkeypatch, qtbot, manager_widget, store, tmp_data_dir
):
    store.create_campaign("WithNote")
    manager_widget.refresh_list()
    # select
    for i in range(manager_widget.list_widget.count()):
        it = manager_widget.list_widget.item(i)
        if it.data(Qt.UserRole) == "WithNote":
            manager_widget.list_widget.setCurrentRow(i)
            break

    # simulate opening the note editor dialog: monkeypatch NoteEditorDialog to provide text

    # create an instance and simulate user entering text and accepting - we will replace the class
    class FakeDialog:
        def __init__(self, parent, initial_text=""):
            self._text = "This is a test note"
            self._accepted = True

        def exec(self):
            return QtWidgets.QDialog.Accepted

        def get_text(self):
            return self._text

    monkeypatch.setattr(
        "chroniclemap.gui.campaign_manager.NoteEditorDialog", FakeDialog
    )

    qtbot.mouseClick(manager_widget.note_btn, Qt.LeftButton)
    qtbot.wait(100)
    # verify metadata updated
    meta = store.load_metadata("WithNote")
    assert meta.get("note") == "This is a test note"
