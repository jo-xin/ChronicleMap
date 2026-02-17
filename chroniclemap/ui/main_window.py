# chroniclemap/ui/main_window.py
from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool, QTimer, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import FilterType
from chroniclemap.services.storage_service import StorageService
from chroniclemap.ui.campaign_manager import CampaignManagerDialog
from chroniclemap.ui.import_dialog import ImportDialog
from chroniclemap.ui.player_viewmodel import PlayerViewModel
from chroniclemap.ui.viewmodels import AppViewModel, CampaignViewModel
from chroniclemap.ui.widgets.canvas_view import CanvasView

DEFAULT_BASE_DIR = Path.home() / ".chroniclemap_data"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChronicleMap — Import Enhanced")
        self.resize(1200, 800)

        # services & viewmodels
        self.storage_service = StorageService(DEFAULT_BASE_DIR)
        self.app_vm = AppViewModel(self.storage_service)
        self.campaign_vm: Optional[CampaignViewModel] = None
        self.player_vm: Optional[PlayerViewModel] = None

        # thread pool
        self._pool = QThreadPool.globalInstance()

        # enable drag & drop
        self.setAcceptDrops(True)

        # menu
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        manage_act = QAction("Manage Campaigns", self)
        manage_act.triggered.connect(self.on_manage_campaigns)
        file_menu.addAction(manage_act)

        # central layout: left controls | center canvas | right meta
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)

        # left: control column (play + import settings)
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)

        # playback area
        left_layout.addWidget(QLabel("Playback controls"))
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.on_play_pause)
        left_layout.addWidget(self.play_btn)

        # import settings group
        imp_box = QGroupBox("Import Settings")
        imp_layout = QVBoxLayout(imp_box)

        imp_layout.addWidget(QLabel("Filter (select for next import):"))
        # radio buttons for each FilterType
        self.filter_radios = {}
        filters_widget = QWidget()
        filt_layout = QVBoxLayout(filters_widget)
        for f in list(FilterType):
            rb = QRadioButton(f.value)
            filt_layout.addWidget(rb)
            self.filter_radios[f.value] = rb
        # default select first
        first_key = list(self.filter_radios.keys())[0]
        self.filter_radios[first_key].setChecked(True)
        imp_layout.addWidget(filters_widget)

        # time interval setting
        time_h = QHBoxLayout()
        time_h.addWidget(QLabel("Default interval:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 9999)
        self.interval_spin.setValue(1)
        time_h.addWidget(self.interval_spin)
        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["days", "months", "years"])
        self.interval_unit.setCurrentText("years")
        time_h.addWidget(self.interval_unit)
        imp_layout.addLayout(time_h)

        # import buttons
        btn_h = QHBoxLayout()
        self.import_btn = QPushButton("Import from File...")
        self.import_btn.clicked.connect(self.on_import_file_clicked)
        self.paste_btn = QPushButton("Paste from Clipboard")
        self.paste_btn.clicked.connect(self.on_paste_clicked)
        btn_h.addWidget(self.import_btn)
        btn_h.addWidget(self.paste_btn)
        imp_layout.addLayout(btn_h)

        left_layout.addWidget(imp_box)
        left_layout.addStretch(1)

        # center: canvas and placeholders
        center_col = QWidget()
        center_layout = QVBoxLayout(center_col)
        self.canvas = CanvasView()
        center_layout.addWidget(self.canvas, 1)
        self.time_slider_label = QLabel("Time axis (placeholder)")
        self.ruler_track_label = QLabel("Ruler axis (placeholder)")
        center_layout.addWidget(self.time_slider_label)
        center_layout.addWidget(self.ruler_track_label)

        # right: metadata / notes
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.addWidget(QLabel("Campaign metadata"))
        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        right_layout.addWidget(self.meta_text)
        right_layout.addWidget(QLabel("Rulers (placeholder)"))
        self.ruler_list = QListWidget()
        right_layout.addWidget(self.ruler_list)

        # add columns to layout (splitter)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_col)
        splitter.addWidget(center_col)
        splitter.addWidget(right_col)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        h_layout.addWidget(splitter)

        # connect app_vm signals
        self.app_vm.campaign_opened.connect(self.on_campaign_opened)

        # timer to drive player tick
        self.timer = QTimer(self)
        self.timer.setInterval(100)  # 100 ms
        self.timer.timeout.connect(self._on_tick)
        self.timer.stop()

    # ------------- drag & drop ----------------
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            # accept if any url is a local file
            for u in mime.urls():
                if u.isLocalFile():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            for u in mime.urls():
                if u.isLocalFile():
                    local = Path(u.toLocalFile())
                    # open import dialog for first file
                    self._open_import_dialog_with_path(local)
                    break

    # ------------- clipboard paste ----------------
    def on_paste_clicked(self):
        cb = QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            QMessageBox.warning(self, "Clipboard", "No image found in clipboard.")
            return
        # save to temporary file
        tmp_dir = Path(tempfile.gettempdir())
        tmp_file = tmp_dir / f"chroniclemap_clip_{int(datetime.now().timestamp())}.png"
        # QImage.save works
        img.save(str(tmp_file))
        self._open_import_dialog_with_path(tmp_file)

    # ------------- file import button ----------------
    def on_import_file_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select image to import")
        if not path:
            return
        self._open_import_dialog_with_path(Path(path))

    # helper to get selected filter and interval
    def _get_selected_filter(self) -> str:
        for k, rb in self.filter_radios.items():
            if rb.isChecked():
                return k
        return list(self.filter_radios.keys())[0]

    def _get_interval_setting(self) -> tuple[int, str]:
        return (int(self.interval_spin.value()), str(self.interval_unit.currentText()))

    # open import dialog
    def _open_import_dialog_with_path(self, img_path: Path):
        if not self.campaign_vm or not self.campaign_vm.campaign:
            QMessageBox.warning(
                self, "No campaign", "Please open or create a campaign first."
            )
            return
        filter_choice = self._get_selected_filter()
        interval = self._get_interval_setting()
        dlg = ImportDialog(
            storage_service=self.storage_service,
            campaign=self.campaign_vm.campaign,
            image_path=img_path,
            initial_filter=filter_choice,
            default_interval=interval,
            parent=self,
        )
        res = dlg.exec()
        # if accepted, reload campaign and emit snapshot update
        if res == QDialog.Accepted:
            try:
                self.campaign_vm.reload()
            except Exception:
                # fallback: attempt to reload via storage
                try:
                    c = self.storage_service.load_campaign(
                        self.campaign_vm.campaign.path
                    )
                    self.campaign_vm.campaign = c
                except Exception:
                    pass
            if self.player_vm:
                self.player_vm._emit_time_and_snapshot()

    # ------------- rest of MainWindow (unchanged core playback wiring) --------------
    @Slot()
    def on_manage_campaigns(self):
        dlg = CampaignManagerDialog(self.app_vm, parent=self)
        dlg.exec()

    @Slot(object)
    def on_campaign_opened(self, campaign):
        # create campaign-scoped viewmodel
        self.campaign_vm = CampaignViewModel(campaign, self.storage_service)
        # create player viewmodel
        self.player_vm = PlayerViewModel(campaign)
        # connect player's signals to UI
        self.player_vm.time_changed.connect(self._on_time_changed)
        self.player_vm.snapshot_changed.connect(self._on_snapshot_changed)
        self.player_vm.playing_changed.connect(self._on_playing_changed)

        # update UI metadata
        self.setWindowTitle(f"ChronicleMap — {campaign.name}")
        self.meta_text.setPlainText(
            f"Campaign: {campaign.name}\nPath: {campaign.path}\nCreated: {campaign.created_at}"
        )
        self.ruler_list.clear()
        for r in campaign.rulers:
            self.ruler_list.addItem(r.display_name or r.full_name or r.id)

        # ensure canvas cleared initially and show first available snapshot
        self.canvas.set_image(None)
        # emit initial state
        self.player_vm._emit_time_and_snapshot()

    def on_play_pause(self):
        if not self.player_vm:
            return
        if not self.player_vm.engine.playing:
            self.player_vm.play()
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.player_vm.pause()
            if self.timer.isActive():
                self.timer.stop()

    def _on_tick(self):
        # forward to player viewmodel
        if not self.player_vm:
            return
        dt = self.timer.interval() / 1000.0
        self.player_vm.tick(dt)

    def _on_time_changed(self, d):
        # update date display in status bar
        try:
            self.statusBar().showMessage(f"Date: {d.isoformat()}")
        except Exception:
            self.statusBar().showMessage(f"Date: {str(d)}")

    def _on_snapshot_changed(self, path):
        # path may be None
        if path:
            self.canvas.set_image(path)
            self.statusBar().showMessage(f"Showing: {Path(path).name}")
        else:
            self.canvas.set_image(None)
            self.statusBar().showMessage("No snapshot")

    def _on_playing_changed(self, playing):
        self.play_btn.setText("Pause" if playing else "Play")
        if not playing and self.timer.isActive():
            self.timer.stop()


def run_app():
    app = QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec())
