from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import (
    FilterType,
    GameDate,
    Rank,
    RankPeriod,
    Ruler,
    new_ruler,
)
from chroniclemap.gui.texts import tr
from chroniclemap.storage.manager import StorageManager
from chroniclemap.temporal.engine import TemporalEngine


def _fmt_date(value: Optional[GameDate]) -> str:
    return value.to_iso() if value else "-"


RANK_ORDER = {
    Rank.NONE: 0,
    Rank.ADVENTURE: 1,
    Rank.COUNTY: 2,
    Rank.DUCHY: 3,
    Rank.KINGDOM: 4,
    Rank.EMPIRE: 5,
    Rank.HEGEMONY: 6,
}

RANK_BORDER_COLORS = {
    Rank.HEGEMONY: "#ff2b2b",
    Rank.EMPIRE: "#7a3cff",
    Rank.KINGDOM: "#d4af37",
    Rank.DUCHY: "#00bcd4",
    Rank.COUNTY: "#2ecc71",
    Rank.ADVENTURE: "#ff66cc",
    Rank.NONE: "#ffffff",
}

RANK_FILL_COLORS = {
    Rank.HEGEMONY: "#ff5a5a",
    Rank.EMPIRE: "#8f5bff",
    Rank.KINGDOM: "#f0ca55",
    Rank.DUCHY: "#45d7e6",
    Rank.COUNTY: "#5ddb8f",
    Rank.ADVENTURE: "#ff89d8",
    Rank.NONE: "#d6d6d6",
}


class RulerTimelineWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ord_min: Optional[int] = None
        self._ord_max: Optional[int] = None
        self._current_ord: Optional[int] = None
        self._segments: list[dict] = []
        self._groups: list[dict] = []
        self.setMinimumHeight(62)
        self.setMaximumHeight(76)

    def set_range(self, ord_min: Optional[int], ord_max: Optional[int]) -> None:
        self._ord_min = ord_min
        self._ord_max = ord_max
        self.update()

    def set_current_ordinal(self, ordinal: Optional[int]) -> None:
        self._current_ord = ordinal
        self.update()

    def _pick_rank_for_interval(
        self, rank_periods: list[RankPeriod], start_ord: int, end_ord: int
    ) -> Rank:
        best = Rank.NONE
        best_score = RANK_ORDER[best]
        for rp in rank_periods:
            rp_start = rp.from_date.to_ordinal(False)
            rp_end = (rp.to_date or GameDate(9999, 12, 31)).to_ordinal(False)
            if rp_end < start_ord or rp_start > end_ord:
                continue
            score = RANK_ORDER.get(rp.rank, 0)
            if score > best_score:
                best = rp.rank
                best_score = score
        return best

    def set_rulers(self, rulers: list[Ruler]) -> None:
        self._segments = []
        self._groups = []
        if (
            self._ord_min is None
            or self._ord_max is None
            or self._ord_min >= self._ord_max
        ):
            self.update()
            return

        for ruler in rulers:
            p_start = ruler.player_start_date or ruler.start_date
            p_end = ruler.player_end_date or ruler.end_date
            if p_start is None or p_end is None:
                continue
            p_start_ord = max(self._ord_min, p_start.to_ordinal(False))
            p_end_ord = min(self._ord_max, p_end.to_ordinal(False))
            if p_end_ord < p_start_ord:
                continue

            cuts = {p_start_ord, p_end_ord + 1}
            for rp in ruler.rank_periods:
                rp_s = max(p_start_ord, rp.from_date.to_ordinal(False))
                rp_e = min(
                    p_end_ord,
                    (rp.to_date.to_ordinal(False) if rp.to_date else p_end_ord),
                )
                if rp_e >= rp_s:
                    cuts.add(rp_s)
                    cuts.add(rp_e + 1)
            sorted_cuts = sorted(cuts)
            ruler_segments = []
            for i in range(len(sorted_cuts) - 1):
                s = sorted_cuts[i]
                e = sorted_cuts[i + 1] - 1
                if e < s:
                    continue
                rank = self._pick_rank_for_interval(ruler.rank_periods, s, e)
                ruler_segments.append(
                    {
                        "start": s,
                        "end": e,
                        "rank": rank,
                        "color": RANK_FILL_COLORS.get(rank, "#d6d6d6"),
                        "ruler_id": ruler.id,
                    }
                )
            if not ruler_segments:
                continue
            self._segments.extend(ruler_segments)
            self._groups.append(
                {
                    "start": ruler_segments[0]["start"],
                    "end": ruler_segments[-1]["end"],
                    "ruler_id": ruler.id,
                    "label": (ruler.display_name or ruler.full_name or "Unknown"),
                }
            )

        self.update()

    def _x_for_ordinal(self, ordinal: int, left: int, width: int) -> int:
        if (
            self._ord_min is None
            or self._ord_max is None
            or self._ord_max == self._ord_min
        ):
            return left
        ratio = (ordinal - self._ord_min) / (self._ord_max - self._ord_min)
        return left + int(ratio * width)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(4, 6, -4, -6)

        p.fillRect(rect, QColor("#1f1f1f"))
        bar_rect = rect.adjusted(6, 6, -6, -20)
        if bar_rect.width() <= 0 or bar_rect.height() <= 0:
            return

        p.fillRect(bar_rect, QColor("#5f5f5f"))

        if (
            self._ord_min is None
            or self._ord_max is None
            or self._ord_min >= self._ord_max
        ):
            p.setPen(QColor("#d0d0d0"))
            p.drawText(rect, Qt.AlignCenter, tr("player.ruler_tl_empty"))
            p.end()
            return

        for group in self._groups:
            x1 = self._x_for_ordinal(group["start"], bar_rect.left(), bar_rect.width())
            x2 = self._x_for_ordinal(group["end"], bar_rect.left(), bar_rect.width())
            if x2 <= x1:
                x2 = x1 + 1
            group_rect = bar_rect.adjusted(0, -2, 0, 2)
            group_rect.setLeft(x1)
            group_rect.setRight(x2)
            active = (
                self._current_ord is not None
                and group["start"] <= self._current_ord <= group["end"]
            )
            pen = QPen(QColor("#f5f5f5") if active else QColor("#bdbdbd"))
            pen.setWidth(2 if active else 1)
            p.setPen(pen)
            p.drawRect(group_rect)

            p.setPen(QColor("#e8e8e8"))
            p.drawText(
                x1 + 2,
                bar_rect.bottom() + 14,
                max(1, x2 - x1 - 3),
                12,
                Qt.AlignLeft | Qt.AlignVCenter,
                str(group["label"]),
            )

        for seg in self._segments:
            x1 = self._x_for_ordinal(seg["start"], bar_rect.left(), bar_rect.width())
            x2 = self._x_for_ordinal(seg["end"], bar_rect.left(), bar_rect.width())
            if x2 <= x1:
                x2 = x1 + 1
            seg_rect = bar_rect.adjusted(1, 1, -1, -1)
            seg_rect.setLeft(x1)
            seg_rect.setRight(x2)
            p.fillRect(seg_rect, QColor(seg["color"]))

        if self._current_ord is not None:
            cx = self._x_for_ordinal(
                self._current_ord, bar_rect.left(), bar_rect.width()
            )
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawLine(cx, bar_rect.top() - 2, cx, bar_rect.bottom() + 2)

        p.end()


class RulerEditorDialog(QDialog):
    def __init__(
        self,
        ruler: Ruler,
        campaign_path: Optional[str],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("ruler_editor.title"))
        self.resize(760, 600)
        self._ruler = ruler
        self._campaign_path = Path(campaign_path) if campaign_path else None
        self._portrait_source_path: Optional[Path] = None
        self._portrait_from_clipboard = None
        self._remove_portrait = False

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.full_name_edit = QLineEdit(ruler.full_name or "")
        self.display_name_edit = QLineEdit(ruler.display_name or "")
        self.epithet_edit = QLineEdit(ruler.epithet or "")
        self.birth_date_edit = QLineEdit(
            ruler.birth_date.to_iso() if ruler.birth_date else ""
        )
        self.death_date_edit = QLineEdit(
            ruler.death_date.to_iso() if ruler.death_date else ""
        )
        self.start_date_edit = QLineEdit(
            ruler.start_date.to_iso() if ruler.start_date else ""
        )
        self.end_date_edit = QLineEdit(
            ruler.end_date.to_iso() if ruler.end_date else ""
        )
        self.player_start_date_edit = QLineEdit(
            ruler.player_start_date.to_iso() if ruler.player_start_date else ""
        )
        self.player_end_date_edit = QLineEdit(
            ruler.player_end_date.to_iso() if ruler.player_end_date else ""
        )
        self.notes_edit = QTextEdit(ruler.notes or "")
        self.notes_edit.setMaximumHeight(120)

        for w in [
            self.birth_date_edit,
            self.death_date_edit,
            self.start_date_edit,
            self.end_date_edit,
            self.player_start_date_edit,
            self.player_end_date_edit,
        ]:
            w.setPlaceholderText(tr("ruler_editor.date_placeholder"))

        form.addRow(tr("ruler_editor.full_name"), self.full_name_edit)
        form.addRow(tr("ruler_editor.display_name"), self.display_name_edit)
        form.addRow(tr("ruler_editor.epithet"), self.epithet_edit)
        form.addRow(tr("ruler_editor.birth_date"), self.birth_date_edit)
        form.addRow(tr("ruler_editor.death_date"), self.death_date_edit)
        form.addRow(tr("ruler_editor.reign_start"), self.start_date_edit)
        form.addRow(tr("ruler_editor.reign_end"), self.end_date_edit)
        form.addRow(tr("ruler_editor.player_start"), self.player_start_date_edit)
        form.addRow(tr("ruler_editor.player_end"), self.player_end_date_edit)
        self.portrait_status = QLabel("")
        portrait_btn_row = QHBoxLayout()
        self.portrait_file_btn = QPushButton(tr("ruler_editor.portrait_choose"))
        self.portrait_paste_btn = QPushButton(tr("ruler_editor.portrait_paste"))
        self.portrait_remove_btn = QPushButton(tr("ruler_editor.portrait_remove"))
        portrait_btn_row.addWidget(self.portrait_file_btn)
        portrait_btn_row.addWidget(self.portrait_paste_btn)
        portrait_btn_row.addWidget(self.portrait_remove_btn)
        self.portrait_preview = QLabel()
        self.portrait_preview.setAlignment(Qt.AlignCenter)
        self.portrait_preview.setFixedSize(110, 130)
        self.portrait_preview.setStyleSheet("border: 1px solid #999;")
        form.addRow(tr("ruler_editor.portrait"), self.portrait_status)
        form.addRow("", portrait_btn_row)
        form.addRow("", self.portrait_preview)
        form.addRow(tr("ruler_editor.notes"), self.notes_edit)
        root.addLayout(form)

        rank_group = QGroupBox(tr("ruler_editor.rank_periods"))
        rank_layout = QVBoxLayout(rank_group)
        self.rank_table = QTableWidget(0, 4)
        self.rank_table.setHorizontalHeaderLabels(
            ["From date", "To date", "Rank", "Note"]
        )
        self.rank_table.horizontalHeader().setStretchLastSection(True)
        self.rank_table.verticalHeader().setVisible(False)
        self.rank_table.setSelectionBehavior(QTableWidget.SelectRows)
        rank_layout.addWidget(self.rank_table)

        rank_btns = QHBoxLayout()
        self.rank_add_btn = QPushButton(tr("ruler_editor.rank_add_row"))
        self.rank_del_btn = QPushButton(tr("ruler_editor.rank_delete_row"))
        rank_btns.addWidget(self.rank_add_btn)
        rank_btns.addWidget(self.rank_del_btn)
        rank_btns.addStretch()
        rank_layout.addLayout(rank_btns)
        root.addWidget(rank_group)

        for rp in ruler.rank_periods:
            self._append_rank_row(
                rp.from_date.to_iso(),
                rp.to_date.to_iso() if rp.to_date else "",
                rp.rank.value,
                rp.note or "",
            )

        self.rank_add_btn.clicked.connect(
            lambda: self._append_rank_row("", "", Rank.NONE.value, "")
        )
        self.rank_del_btn.clicked.connect(self._delete_selected_rank_rows)
        self.portrait_file_btn.clicked.connect(self._on_choose_portrait)
        self.portrait_paste_btn.clicked.connect(self._on_paste_portrait)
        self.portrait_remove_btn.clicked.connect(self._on_remove_portrait)
        self._refresh_portrait_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _append_rank_row(
        self, from_date: str, to_date: str, rank_value: str, note: str
    ) -> None:
        row = self.rank_table.rowCount()
        self.rank_table.insertRow(row)
        self.rank_table.setItem(row, 0, QTableWidgetItem(from_date))
        self.rank_table.setItem(row, 1, QTableWidgetItem(to_date))
        rank_combo = QComboBox()
        rank_combo.addItems([r.value for r in Rank])
        if rank_value in [r.value for r in Rank]:
            rank_combo.setCurrentText(rank_value)
        else:
            rank_combo.setCurrentText(Rank.NONE.value)
        self.rank_table.setCellWidget(row, 2, rank_combo)
        self.rank_table.setItem(row, 3, QTableWidgetItem(note))

    def _delete_selected_rank_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.rank_table.selectedIndexes()})
        for row in reversed(rows):
            self.rank_table.removeRow(row)

    def _parse_optional_date(self, text: str) -> Optional[GameDate]:
        value = text.strip()
        if not value:
            return None
        return GameDate.fromiso(value)

    def _resolve_portrait_path(self) -> Optional[Path]:
        if not self._campaign_path or not self._ruler.portrait_path:
            return None
        p = Path(self._ruler.portrait_path)
        if p.is_absolute():
            return p
        return self._campaign_path / p

    def _refresh_portrait_preview(self) -> None:
        pix = None
        if self._remove_portrait:
            self.portrait_status.setText(tr("ruler_editor.portrait_will_remove"))
        elif self._portrait_source_path and self._portrait_source_path.exists():
            pix = QPixmap(str(self._portrait_source_path))
            self.portrait_status.setText(self._portrait_source_path.name)
        elif self._portrait_from_clipboard is not None:
            pix = QPixmap.fromImage(self._portrait_from_clipboard)
            self.portrait_status.setText(tr("ruler_editor.portrait_from_clipboard"))
        else:
            current = self._resolve_portrait_path()
            if current and current.exists():
                pix = QPixmap(str(current))
                self.portrait_status.setText(str(current.name))
            else:
                self.portrait_status.setText(tr("ruler_editor.portrait_none"))

        if pix and not pix.isNull():
            self.portrait_preview.setText("")
            self.portrait_preview.setPixmap(
                pix.scaled(
                    self.portrait_preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            self.portrait_preview.setPixmap(QPixmap())
            self.portrait_preview.setText(tr("ruler_editor.no_image"))

    def _on_choose_portrait(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ruler_editor.portrait_choose"),
            str(Path.home()),
            tr("common.images_filter_ext"),
        )
        if not path:
            return
        self._remove_portrait = False
        self._portrait_source_path = Path(path)
        self._portrait_from_clipboard = None
        self._refresh_portrait_preview()

    def _on_paste_portrait(self) -> None:
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            QMessageBox.information(
                self,
                tr("snapshot_confirm.clipboard_title"),
                tr("snapshot_confirm.clipboard_no_image"),
            )
            return
        self._remove_portrait = False
        self._portrait_from_clipboard = image
        self._portrait_source_path = None
        self._refresh_portrait_preview()

    def _on_remove_portrait(self) -> None:
        self._remove_portrait = True
        self._portrait_source_path = None
        self._portrait_from_clipboard = None
        self._refresh_portrait_preview()

    def _persist_portrait_if_needed(self) -> None:
        if self._remove_portrait:
            self._ruler.portrait_path = None
            return
        if not self._campaign_path:
            return
        if self._portrait_source_path is None and self._portrait_from_clipboard is None:
            return

        portraits_dir = self._campaign_path / "rulers" / "portraits"
        portraits_dir.mkdir(parents=True, exist_ok=True)

        if self._portrait_from_clipboard is not None:
            rel = Path("rulers") / "portraits" / f"{self._ruler.id}.png"
            dst = self._campaign_path / rel
            self._portrait_from_clipboard.save(str(dst), "PNG")
            self._ruler.portrait_path = str(rel)
            return

        src = self._portrait_source_path
        if src is None:
            return
        ext = src.suffix.lower() or ".png"
        rel = Path("rulers") / "portraits" / f"{self._ruler.id}{ext}"
        dst = self._campaign_path / rel
        shutil.copy2(src, dst)
        self._ruler.portrait_path = str(rel)

    def _on_accept(self) -> None:
        try:
            self._ruler.full_name = self.full_name_edit.text().strip() or None
            self._ruler.display_name = self.display_name_edit.text().strip() or None
            self._ruler.epithet = self.epithet_edit.text().strip() or None
            self._ruler.birth_date = self._parse_optional_date(
                self.birth_date_edit.text()
            )
            self._ruler.death_date = self._parse_optional_date(
                self.death_date_edit.text()
            )
            self._ruler.start_date = self._parse_optional_date(
                self.start_date_edit.text()
            )
            self._ruler.end_date = self._parse_optional_date(self.end_date_edit.text())
            self._ruler.player_start_date = self._parse_optional_date(
                self.player_start_date_edit.text()
            )
            self._ruler.player_end_date = self._parse_optional_date(
                self.player_end_date_edit.text()
            )
            self._ruler.notes = self.notes_edit.toPlainText().strip() or None

            rank_periods: list[RankPeriod] = []
            for row in range(self.rank_table.rowCount()):
                from_item = self.rank_table.item(row, 0)
                to_item = self.rank_table.item(row, 1)
                rank_item = self.rank_table.item(row, 2)
                note_item = self.rank_table.item(row, 3)

                from_text = from_item.text().strip() if from_item else ""
                to_text = to_item.text().strip() if to_item else ""
                rank_widget = self.rank_table.cellWidget(row, 2)
                if isinstance(rank_widget, QComboBox):
                    rank_text = rank_widget.currentText().strip()
                else:
                    rank_text = (
                        rank_item.text().strip() if rank_item else Rank.NONE.value
                    )
                note_text = note_item.text().strip() if note_item else ""

                if not from_text:
                    continue
                rp = RankPeriod(
                    from_date=GameDate.fromiso(from_text),
                    to_date=GameDate.fromiso(to_text) if to_text else None,
                    rank=Rank(rank_text),
                    note=note_text or None,
                )
                rank_periods.append(rp)

            self._ruler.rank_periods = rank_periods
            self._persist_portrait_if_needed()
        except Exception as exc:
            QMessageBox.warning(self, tr("ruler_editor.invalid_input"), str(exc))
            return

        self.accept()


class PlayerWindow(QWidget):
    def __init__(
        self,
        campaign_name: str,
        storage_base_dir,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.storage = StorageManager(storage_base_dir)
        self.campaign = self.storage.load_campaign(campaign_name)
        self.engine = TemporalEngine(campaign=self.campaign)
        self._ruler_index = 0
        self._sort_rulers()

        self.setWindowTitle(
            tr("player.title", app=tr("app.name"), campaign=campaign_name)
        )
        self.resize(1280, 820)

        outer = QVBoxLayout(self)
        self.menu_bar = QMenuBar(self)
        outer.addWidget(self.menu_bar)
        root = QHBoxLayout()
        outer.addLayout(root, 1)
        root.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(8)
        root.addLayout(left, 0)

        playback_group = QGroupBox(tr("player.playback"))
        playback_group.setMaximumWidth(320)
        playback_layout = QVBoxLayout(playback_group)

        controls_row = QGridLayout()
        self.play_btn = QPushButton(tr("player.play"))
        self.pause_btn = QPushButton(tr("player.pause"))
        self.prev_btn = QPushButton(tr("player.prev_snapshot"))
        self.next_btn = QPushButton(tr("player.next_snapshot"))
        controls_row.addWidget(self.play_btn, 0, 0)
        controls_row.addWidget(self.pause_btn, 0, 1)
        controls_row.addWidget(self.prev_btn, 1, 0)
        controls_row.addWidget(self.next_btn, 1, 1)
        playback_layout.addLayout(controls_row)

        speed_row = QHBoxLayout()
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setDecimals(2)
        self.speed_spin.setRange(0.01, 10000.0)
        self.speed_unit = QComboBox()
        self.speed_unit.addItems(["days/sec", "months/sec", "years/sec"])
        speed_row.addWidget(QLabel(tr("player.speed")))
        speed_row.addWidget(self.speed_spin)
        speed_row.addWidget(self.speed_unit)
        playback_layout.addLayout(speed_row)
        left.addWidget(playback_group)

        ps = self.campaign.config.playback_speed
        self.speed_spin.setValue(float(ps.get("value", 365)))
        unit = ps.get("units", "days/sec")
        if unit in ["days/sec", "months/sec", "years/sec"]:
            self.speed_unit.setCurrentText(unit)

        self.ruler_group = QGroupBox(tr("player.ruler_profile"))
        self.ruler_group.setMaximumWidth(320)
        ruler_layout = QVBoxLayout(self.ruler_group)
        nav = QHBoxLayout()
        self.ruler_prev_btn = QPushButton("<")
        self.ruler_next_btn = QPushButton(">")
        self.ruler_index_label = QLabel("0 / 0")
        nav.addWidget(self.ruler_prev_btn)
        nav.addWidget(self.ruler_index_label, 1)
        nav.addWidget(self.ruler_next_btn)
        ruler_layout.addLayout(nav)

        self.ruler_portrait = QLabel(tr("player.portrait_placeholder"))
        self.ruler_portrait.setAlignment(Qt.AlignCenter)
        self.ruler_portrait.setMinimumHeight(140)
        self.ruler_portrait.setMaximumHeight(360)
        self.ruler_portrait.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.ruler_portrait.setStyleSheet(
            "border: 1px dashed #888; background: #f3f3f3; color: #666;"
        )
        ruler_layout.addWidget(self.ruler_portrait)

        self.ruler_summary = QLabel("")
        self.ruler_summary.setWordWrap(True)
        self.ruler_summary.setStyleSheet("border: 1px solid #ddd; padding: 6px;")
        self.ruler_summary.setMaximumHeight(210)
        ruler_layout.addWidget(self.ruler_summary)

        edit_row = QHBoxLayout()
        self.edit_ruler_btn = QPushButton(tr("player.edit"))
        self.create_ruler_btn = QPushButton(tr("player.create"))
        edit_row.addWidget(self.edit_ruler_btn)
        edit_row.addWidget(self.create_ruler_btn)
        ruler_layout.addLayout(edit_row)

        ops_row = QHBoxLayout()
        self.delete_ruler_btn = QPushButton(tr("player.delete"))
        self.copy_ruler_btn = QPushButton(tr("player.copy"))
        ops_row.addWidget(self.delete_ruler_btn)
        ops_row.addWidget(self.copy_ruler_btn)
        ruler_layout.addLayout(ops_row)
        left.addWidget(self.ruler_group)
        left.addStretch()

        center = QVBoxLayout()
        root.addLayout(center, 1)

        self.image_label = QLabel(tr("player.no_snapshots"))
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)
        center.addWidget(self.image_label, 5)

        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setSingleStep(1)
        self.timeline_slider.setPageStep(10)
        self.timeline_label = QLabel(tr("player.timeline"))
        center.addWidget(self.timeline_slider)
        center.addWidget(self.timeline_label)

        date_jump_row = QHBoxLayout()
        self.current_date_edit = QLineEdit()
        self.current_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.current_date_edit.setClearButtonEnabled(True)
        self.current_date_jump_btn = QPushButton(tr("player.jump"))
        date_jump_row.addWidget(QLabel(tr("player.current_date")))
        date_jump_row.addWidget(self.current_date_edit)
        date_jump_row.addWidget(self.current_date_jump_btn)
        center.addLayout(date_jump_row)

        self.ruler_timeline = RulerTimelineWidget()
        center.addWidget(QLabel(tr("player.ruler_timeline")))
        center.addWidget(self.ruler_timeline)

        right = QVBoxLayout()
        right.setSpacing(8)
        root.addLayout(right, 0)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([f.value for f in FilterType])
        right.addWidget(QLabel(tr("common.filter")))
        right.addWidget(self.filter_combo)

        self.current_snapshot_label = QLabel("")
        self.current_snapshot_label.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred
        )
        self.current_snapshot_label.setWordWrap(True)
        self.current_snapshot_label.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 3px; padding: 4px;"
        )
        right.addWidget(QLabel(tr("player.snapshot_current")))
        right.addWidget(self.current_snapshot_label)

        note_group = QGroupBox(tr("player.campaign_note"))
        note_layout = QVBoxLayout(note_group)
        self.note_edit = QTextEdit(self.campaign.notes or "")
        self.note_edit.setMinimumHeight(120)
        self.note_edit.setMaximumHeight(220)
        self.note_edit.setPlaceholderText(tr("player.note_placeholder"))
        self.save_note_btn = QPushButton(tr("player.note_save"))
        note_layout.addWidget(self.note_edit)
        note_layout.addWidget(self.save_note_btn)
        right.addWidget(note_group)
        right.addStretch()

        self._setup_menus()

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self.play_btn.clicked.connect(self._on_play)
        self.pause_btn.clicked.connect(self._on_pause)
        self.prev_btn.clicked.connect(self._on_prev_snapshot)
        self.next_btn.clicked.connect(self._on_next_snapshot)
        self.speed_spin.valueChanged.connect(
            lambda v: self._on_speed_changed(v, self.speed_unit.currentText())
        )
        self.speed_unit.currentTextChanged.connect(
            lambda u: self._on_speed_changed(self.speed_spin.value(), u)
        )
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        self.current_date_jump_btn.clicked.connect(self._on_date_jump)
        self.current_date_edit.returnPressed.connect(self._on_date_jump)
        self.filter_combo.currentTextChanged.connect(lambda _txt: self._update_frame())
        self.save_note_btn.clicked.connect(self._on_save_note)
        self.ruler_prev_btn.clicked.connect(self._on_prev_ruler)
        self.ruler_next_btn.clicked.connect(self._on_next_ruler)
        self.edit_ruler_btn.clicked.connect(self._on_edit_ruler)
        self.create_ruler_btn.clicked.connect(self._on_create_ruler)
        self.delete_ruler_btn.clicked.connect(self._on_delete_ruler)
        self.copy_ruler_btn.clicked.connect(self._on_copy_ruler)

        self._init_timeline_range()
        self._update_frame()
        self._refresh_ruler_card()

    def _setup_menus(self) -> None:
        tools_menu = self.menu_bar.addMenu(tr("menu.tools"))
        export_menu = tools_menu.addMenu(tr("menu.export"))

        self.action_export_mp4 = QAction(tr("menu.export.mp4"), self)
        self.action_export_mp4.setEnabled(False)
        self.action_export_gif = QAction(tr("menu.export.gif"), self)
        self.action_export_gif.setEnabled(False)
        export_menu.addAction(self.action_export_mp4)
        export_menu.addAction(self.action_export_gif)

        toys_menu = tools_menu.addMenu(tr("menu.toys"))
        self.action_toy_timewarp = QAction(tr("menu.toys.timewarp"), self)
        self.action_toy_timewarp.triggered.connect(
            lambda: QMessageBox.information(
                self, tr("menu.toys"), tr("menu.toys.message")
            )
        )
        toys_menu.addAction(self.action_toy_timewarp)

        campaign_menu = self.menu_bar.addMenu(tr("menu.campaign"))
        self.action_open_campaign_folder = QAction(
            tr("menu.campaign.open_folder"), self
        )
        self.action_open_campaign_folder.triggered.connect(self._open_campaign_folder)
        campaign_menu.addAction(self.action_open_campaign_folder)

    def _open_campaign_folder(self) -> None:
        if not self.campaign.path:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(self.campaign.path))

    def _init_timeline_range(self) -> None:
        if not self.campaign.snapshots:
            self.timeline_slider.setEnabled(False)
            self.timeline_label.setText(tr("player.timeline_empty"))
            self.ruler_timeline.set_range(None, None)
            self.ruler_timeline.set_rulers(self.campaign.rulers)
            return
        ordinals = [
            s.date.to_ordinal(ignore_leap=False) for s in self.campaign.snapshots
        ]
        self._ord_min = min(ordinals)
        self._ord_max = max(ordinals)
        self.timeline_slider.setEnabled(True)
        self.timeline_slider.setMinimum(self._ord_min)
        self.timeline_slider.setMaximum(self._ord_max)
        self.timeline_slider.setValue(self.engine.get_current_date().to_ordinal(False))
        self.ruler_timeline.set_range(self._ord_min, self._ord_max)
        self.ruler_timeline.set_rulers(self.campaign.rulers)
        self._update_timeline_label()

    def _current_filter(self) -> Optional[FilterType]:
        try:
            return FilterType(self.filter_combo.currentText())
        except Exception:
            return None

    def _on_play(self) -> None:
        self.engine.play()

    def _on_pause(self) -> None:
        self.engine.pause()

    def _on_prev_snapshot(self) -> None:
        cur = self.engine.get_current_date()
        flt = self._current_filter()
        prev = None
        for s in self.campaign.snapshots:
            if flt and s.filter_type != flt:
                continue
            if s.date < cur and (prev is None or s.date > prev.date):
                prev = s
        if prev:
            self.engine.seek(prev.date)
            self._update_frame()

    def _on_next_snapshot(self) -> None:
        nxt = self.engine.step_to_next_snapshot(filter_type=self._current_filter())
        if nxt:
            self._update_frame()

    def _on_speed_changed(self, value: float, unit: str) -> None:
        self.engine.set_playback_speed(unit, value)
        self.campaign.config.playback_speed = {"units": unit, "value": value}
        self.storage.save_campaign(self.campaign)

    def _on_slider_changed(self, value: int) -> None:
        if not hasattr(self, "_ord_min"):
            return
        self.engine.seek(GameDate.from_ordinal(value, ignore_leap=False))
        self._update_frame()

    def _on_date_jump(self) -> None:
        text = self.current_date_edit.text().strip()
        if not text:
            return
        try:
            self.engine.seek(GameDate.fromiso(text))
        except Exception:
            self.current_date_edit.setStyleSheet("border: 1px solid #cc3333;")
            return
        self.current_date_edit.setStyleSheet("")
        self._update_frame()

    def _on_tick(self) -> None:
        if not self.engine.playing:
            return
        self.engine.tick(self._timer.interval() / 1000.0)
        self._update_frame()

    def _on_save_note(self) -> None:
        self.campaign.notes = self.note_edit.toPlainText()
        self.storage.save_campaign(self.campaign)

    def _abs_portrait_path(self, portrait_path: Optional[str]) -> Optional[Path]:
        if not portrait_path:
            return None
        p = Path(portrait_path)
        if p.is_absolute():
            return p
        if not self.campaign.path:
            return None
        return Path(self.campaign.path) / p

    def _cleanup_portrait_if_unused(self, old_portrait_path: Optional[str]) -> None:
        abs_old = self._abs_portrait_path(old_portrait_path)
        if not abs_old or not abs_old.exists():
            return
        old_resolved = abs_old.resolve()
        for r in self.campaign.rulers:
            candidate = self._abs_portrait_path(r.portrait_path)
            if candidate and candidate.exists() and candidate.resolve() == old_resolved:
                return
        try:
            abs_old.unlink()
            parent = abs_old.parent
            if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
            grand = parent.parent
            if grand.exists() and grand.is_dir() and not any(grand.iterdir()):
                grand.rmdir()
        except Exception:
            pass

    def _set_portrait_filled(self, pixmap: Optional[QPixmap]) -> None:
        if pixmap is None or pixmap.isNull():
            self.ruler_portrait.setPixmap(QPixmap())
            self.ruler_portrait.setText(tr("player.portrait_placeholder"))
            self.ruler_portrait.setMinimumHeight(140)
            return
        available_w = max(1, self.ruler_group.width() - 24)
        scaled = pixmap.scaledToWidth(available_w, Qt.SmoothTransformation)
        max_h = 360
        if scaled.height() > max_h:
            scaled = scaled.scaledToHeight(max_h, Qt.SmoothTransformation)
        self.ruler_portrait.setMinimumHeight(min(max_h, scaled.height()))
        self.ruler_portrait.setText("")
        self.ruler_portrait.setPixmap(scaled)

    def _highest_rank(self, ruler: Ruler) -> Rank:
        if not ruler.rank_periods:
            return Rank.NONE
        best = Rank.NONE
        best_score = RANK_ORDER[best]
        for rp in ruler.rank_periods:
            score = RANK_ORDER.get(rp.rank, 0)
            if score > best_score:
                best = rp.rank
                best_score = score
        return best

    def _truncate_note(
        self, text: str, max_lines: int = 5, max_chars: int = 320
    ) -> str:
        lines = text.strip().splitlines()
        short_lines = lines[:max_lines]
        result = "\n".join(short_lines).strip()
        clipped = len(lines) > max_lines
        if len(result) > max_chars:
            result = result[:max_chars].rstrip()
            clipped = True
        if clipped and result:
            result += tr("player.ruler_note_more")
        return result

    def _display_name_line(self, ruler: Ruler) -> str:
        base_name = (ruler.display_name or ruler.full_name or "").strip()
        epi = (ruler.epithet or "").strip()
        if epi and base_name:
            return f"{epi} {base_name}"
        if epi:
            return epi
        if base_name:
            return base_name
        return "-"

    def _current_ruler(self) -> Optional[Ruler]:
        if not self.campaign.rulers:
            return None
        if self._ruler_index >= len(self.campaign.rulers):
            self._ruler_index = len(self.campaign.rulers) - 1
        if self._ruler_index < 0:
            self._ruler_index = 0
        return self.campaign.rulers[self._ruler_index]

    def _sort_rulers(self) -> None:
        # No player_start_date comes first; otherwise ascending by date.
        self.campaign.rulers.sort(
            key=lambda r: (
                0 if r.player_start_date is None else 1,
                r.player_start_date.to_ordinal(False) if r.player_start_date else 0,
            )
        )

    def _save_and_refresh_rulers(self, keep_ruler_id: Optional[str] = None) -> None:
        self._sort_rulers()
        if keep_ruler_id:
            for idx, ruler in enumerate(self.campaign.rulers):
                if ruler.id == keep_ruler_id:
                    self._ruler_index = idx
                    break
        if not self.campaign.rulers:
            self._ruler_index = 0
        elif self._ruler_index >= len(self.campaign.rulers):
            self._ruler_index = len(self.campaign.rulers) - 1
        self.storage.save_campaign(self.campaign)
        self.ruler_timeline.set_rulers(self.campaign.rulers)
        self._refresh_ruler_card()

    def _on_prev_ruler(self) -> None:
        if not self.campaign.rulers:
            return
        self._ruler_index = (self._ruler_index - 1) % len(self.campaign.rulers)
        self._refresh_ruler_card()

    def _on_next_ruler(self) -> None:
        if not self.campaign.rulers:
            return
        self._ruler_index = (self._ruler_index + 1) % len(self.campaign.rulers)
        self._refresh_ruler_card()

    def _on_edit_ruler(self) -> None:
        ruler = self._current_ruler()
        if ruler is None:
            self._on_create_ruler()
            return
        old_portrait_path = ruler.portrait_path
        dlg = RulerEditorDialog(ruler, self.campaign.path, self)
        if dlg.exec() == QDialog.Accepted:
            self._save_and_refresh_rulers(keep_ruler_id=ruler.id)
            if old_portrait_path != ruler.portrait_path:
                self._cleanup_portrait_if_unused(old_portrait_path)

    def _on_create_ruler(self) -> None:
        ruler = new_ruler()
        dlg = RulerEditorDialog(ruler, self.campaign.path, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.campaign.rulers.append(ruler)
        self._save_and_refresh_rulers(keep_ruler_id=ruler.id)

    def _on_delete_ruler(self) -> None:
        ruler = self._current_ruler()
        if ruler is None:
            return
        old_portrait_path = ruler.portrait_path
        reply = QMessageBox.question(
            self,
            tr("player.delete_ruler_title"),
            tr("player.delete_ruler_body"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.campaign.rulers = [r for r in self.campaign.rulers if r.id != ruler.id]
        self._save_and_refresh_rulers()
        self._cleanup_portrait_if_unused(old_portrait_path)

    def _on_copy_ruler(self) -> None:
        ruler = self._current_ruler()
        if ruler is None:
            return
        copied = Ruler.from_dict(ruler.to_dict())
        copied.id = str(uuid.uuid4())
        if copied.display_name:
            copied.display_name = f"{copied.display_name} (copy)"
        elif copied.full_name:
            copied.full_name = f"{copied.full_name} (copy)"
        self.campaign.rulers.append(copied)
        self._save_and_refresh_rulers(keep_ruler_id=copied.id)

    def _refresh_ruler_card(self) -> None:
        ruler = self._current_ruler()
        total = len(self.campaign.rulers)
        if ruler is None:
            self.ruler_index_label.setText("0 / 0")
            self.ruler_summary.setText(tr("player.ruler_none"))
            self.edit_ruler_btn.setEnabled(True)
            self.create_ruler_btn.setEnabled(True)
            self.ruler_prev_btn.setEnabled(False)
            self.ruler_next_btn.setEnabled(False)
            self.delete_ruler_btn.setEnabled(False)
            self.copy_ruler_btn.setEnabled(False)
            self._set_portrait_filled(None)
            self.ruler_portrait.setStyleSheet(
                "border: 2px solid #ffffff; background: #f3f3f3; color: #666;"
            )
            return

        self.edit_ruler_btn.setEnabled(True)
        self.create_ruler_btn.setEnabled(True)
        self.ruler_prev_btn.setEnabled(total > 1)
        self.ruler_next_btn.setEnabled(total > 1)
        self.delete_ruler_btn.setEnabled(True)
        self.copy_ruler_btn.setEnabled(True)
        self.ruler_index_label.setText(f"{self._ruler_index + 1} / {total}")

        top_rank = self._highest_rank(ruler)
        border_color = RANK_BORDER_COLORS.get(top_rank, "#ffffff")
        self.ruler_portrait.setStyleSheet(
            f"border: 3px solid {border_color}; background: #f3f3f3; color: #666;"
        )
        portrait_pix = None
        if ruler.portrait_path and self.campaign.path:
            portrait_path = Path(ruler.portrait_path)
            if not portrait_path.is_absolute():
                portrait_path = Path(self.campaign.path) / portrait_path
            if portrait_path.exists():
                portrait_pix = QPixmap(str(portrait_path))
        if portrait_pix and not portrait_pix.isNull():
            self._set_portrait_filled(portrait_pix)
        else:
            self._set_portrait_filled(None)

        lines = [
            self._display_name_line(ruler),
            ruler.full_name or "-",
            tr(
                "player.ruler_life",
                start=_fmt_date(ruler.birth_date),
                end=_fmt_date(ruler.death_date),
            ),
            tr(
                "player.ruler_reign",
                start=_fmt_date(ruler.start_date),
                end=_fmt_date(ruler.end_date),
            ),
            tr(
                "player.ruler_player",
                start=_fmt_date(ruler.player_start_date),
                end=_fmt_date(ruler.player_end_date),
            ),
        ]
        if ruler.notes:
            note_short = self._truncate_note(ruler.notes)
            if note_short:
                lines.append(f"Note: {note_short}")
        self.ruler_summary.setText("\n".join(lines))
        self.ruler_timeline.set_rulers(self.campaign.rulers)

    def _update_frame(self) -> None:
        cur_date = self.engine.get_current_date()
        snap = self.engine.get_snapshot_for(
            d=cur_date,
            filter_type=self._current_filter(),
            prefer_latest_before=True,
        )
        if hasattr(self, "_ord_min"):
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(cur_date.to_ordinal(False))
            self.timeline_slider.blockSignals(False)
        self._update_timeline_label()

        self.current_date_edit.blockSignals(True)
        self.current_date_edit.setText(cur_date.to_iso())
        self.current_date_edit.blockSignals(False)
        self.ruler_timeline.set_current_ordinal(cur_date.to_ordinal(False))

        if snap:
            self.current_snapshot_label.setText(os.path.basename(snap.path))
            pix = QPixmap(snap.path)
            if not pix.isNull():
                pix = pix.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(pix)
            else:
                self.image_label.setText(tr("player.image_na"))
        else:
            self.current_snapshot_label.setText(tr("player.snapshot_na"))
            self.image_label.setText(tr("player.no_snapshot_date"))

    def _update_timeline_label(self) -> None:
        if not hasattr(self, "_ord_min") or not hasattr(self, "_ord_max"):
            return
        d_min = GameDate.from_ordinal(self._ord_min, ignore_leap=False)
        d_max = GameDate.from_ordinal(self._ord_max, ignore_leap=False)
        self.timeline_label.setText(
            tr("player.timeline_range", dmin=d_min.to_iso(), dmax=d_max.to_iso())
        )
