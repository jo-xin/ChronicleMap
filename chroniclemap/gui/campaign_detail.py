from __future__ import annotations

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
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.gui.campaign_store import CampaignStore
from chroniclemap.gui.import_widget import ImportWidget
from chroniclemap.gui.player_window import PlayerWindow
from chroniclemap.storage.manager import StorageManager
from chroniclemap.vision.ocr import TesseractOCRProvider


class CampaignDetailWindow(QWidget):
    """
    简单的活动详情/导入界面：
    - 上半部分：当前活动下已有的快照列表
    - 下半部分：ImportWidget，用于从文件/剪贴板/拖拽导入新的截图
    """

    def __init__(
        self,
        campaign_name: str,
        store: CampaignStore,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.campaign_name = campaign_name
        self.store = store
        # 使用与 CampaignStore 相同的根目录构造 StorageManager
        self.storage = StorageManager(self.store.root)
        # 默认使用 MockOCR：先从文件名提取日期，必要时再尝试 OCR
        self.ocr = TesseractOCRProvider()

        self.setWindowTitle(f"ChronicleMap — {campaign_name}")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        # 顶部信息与快照列表
        info = QLabel(f"Campaign: {campaign_name}")
        layout.addWidget(info)

        # 左侧：快照列表（允许多选）
        top_layout = QHBoxLayout()
        layout.addLayout(top_layout, 1)

        self.snapshot_list = QListWidget()
        self.snapshot_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        top_layout.addWidget(self.snapshot_list, 2)

        # 右侧：预览 + 单条编辑 + 批量编辑
        right_panel = QVBoxLayout()
        top_layout.addLayout(right_panel, 3)

        # 预览区域
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel("No snapshot selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        preview_layout.addWidget(self.preview_label)
        self.open_external_btn = QPushButton("Open in default viewer")
        preview_layout.addWidget(self.open_external_btn)
        preview_group.setLayout(preview_layout)
        right_panel.addWidget(preview_group)

        # 单条编辑区域
        single_group = QGroupBox("Edit selected snapshot")
        single_form = QFormLayout()
        self.single_date_edit = QLineEdit()
        self.single_filter_combo = QComboBox()
        self.single_filter_combo.addItems([f.value for f in FilterType])
        self.single_apply_btn = QPushButton("Apply to this snapshot")
        single_form.addRow("Date (YYYY-MM-DD):", self.single_date_edit)
        single_form.addRow("Filter:", self.single_filter_combo)
        single_form.addRow(self.single_apply_btn)
        single_group.setLayout(single_form)
        right_panel.addWidget(single_group)

        # 批量编辑区域
        bulk_group = QGroupBox("Bulk edit selected snapshots")
        bulk_layout = QVBoxLayout()

        # 批量修改滤镜
        bulk_filter_row = QHBoxLayout()
        self.bulk_filter_combo = QComboBox()
        self.bulk_filter_combo.addItems([f.value for f in FilterType])
        self.bulk_filter_btn = QPushButton("Set filter for all selected")
        bulk_filter_row.addWidget(self.bulk_filter_combo)
        bulk_filter_row.addWidget(self.bulk_filter_btn)
        bulk_layout.addLayout(bulk_filter_row)

        # 批量日期偏移
        bulk_date_row = QHBoxLayout()
        self.bulk_sign_combo = QComboBox()
        self.bulk_sign_combo.addItems(["+", "-"])
        self.bulk_delta_spin = QSpinBox()
        self.bulk_delta_spin.setMinimum(1)
        self.bulk_delta_spin.setMaximum(100000)
        self.bulk_unit_combo = QComboBox()
        self.bulk_unit_combo.addItems(["days", "years"])
        self.bulk_date_btn = QPushButton("Apply date offset")
        bulk_date_row.addWidget(self.bulk_sign_combo)
        bulk_date_row.addWidget(self.bulk_delta_spin)
        bulk_date_row.addWidget(self.bulk_unit_combo)
        bulk_date_row.addWidget(self.bulk_date_btn)
        bulk_layout.addLayout(bulk_date_row)

        bulk_group.setLayout(bulk_layout)
        right_panel.addWidget(bulk_group)

        # 导入区域
        self.import_widget = ImportWidget(
            campaign_name=campaign_name,
            campaign_store=self.store,
            storage_manager=self.storage,
            ocr_provider=self.ocr,
            parent=self,
        )
        layout.addWidget(self.import_widget, 0)

        # 底部按钮栏
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Snapshots")
        self.open_player_btn = QPushButton("Open Player View")
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.open_player_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.refresh_btn.clicked.connect(self.refresh_snapshots)
        self.open_player_btn.clicked.connect(self._open_player)
        self.close_btn.clicked.connect(self.close)

        # 当 ImportWidget 导入成功或滤镜变化时自动刷新列表
        if hasattr(self.import_widget, "snapshot_added"):
            self.import_widget.snapshot_added.connect(
                lambda _snap: self.refresh_snapshots()
            )
        if hasattr(self.import_widget, "filter_changed"):
            self.import_widget.filter_changed.connect(
                lambda _name: self.refresh_snapshots()
            )

        # 列表选择变化时更新右侧视图
        self.snapshot_list.itemSelectionChanged.connect(self._on_selection_changed)

        # 信号绑定：单条编辑 / 打开外部查看器 / 批量编辑
        self.open_external_btn.clicked.connect(self._open_selected_external)
        self.single_apply_btn.clicked.connect(self._apply_single_edit)
        self.bulk_filter_btn.clicked.connect(self._apply_bulk_filter)
        self.bulk_date_btn.clicked.connect(self._apply_bulk_date_offset)

        self.refresh_snapshots()

    def refresh_snapshots(self) -> None:
        """从 metadata 中读取所有快照并刷新列表显示。"""
        self.snapshot_list.clear()
        try:
            meta = self.store.load_metadata(self.campaign_name) or {}
        except FileNotFoundError:
            return

        snaps = meta.get("snapshots", [])
        # 当前选中的滤镜（若 ImportWidget 可用）
        current_filter: Optional[str] = None
        try:
            if hasattr(self.import_widget, "current_filter"):
                current_filter = self.import_widget.current_filter()
        except Exception:
            current_filter = None

        for s in snaps:
            date = s.get("date") or ""
            filter_type = s.get("filter_type") or s.get("filter") or ""
            # 根据当前滤镜筛选
            if current_filter and filter_type and filter_type != current_filter:
                continue
            path = s.get("path") or ""
            text = f"{date} [{filter_type}] | {path}"
            item = QListWidgetItem(text)
            # 把原始快照 dict 挂到 item 上，方便后续找到 id/path 等
            item.setData(Qt.UserRole, s)
            self.snapshot_list.addItem(item)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_snapshot_dicts(self) -> List[dict]:
        """返回当前选中的 snapshot 字典列表。"""
        result: List[dict] = []
        for it in self.snapshot_list.selectedItems():
            data = it.data(Qt.UserRole)
            if isinstance(data, dict):
                result.append(data)
        return result

    def _load_campaign(self):
        """从磁盘加载当前 campaign 对象。"""
        # StorageManager.create_campaign_on_disk 将路径放在 root/Campaigns 下
        return self.storage.load_campaign(self.campaign_name)

    def _on_selection_changed(self) -> None:
        """根据当前选择刷新预览和单条编辑表单。"""
        selected = self._selected_snapshot_dicts()
        if not selected:
            self.preview_label.setText("No snapshot selected")
            self.single_date_edit.clear()
            return

        first = selected[0]
        # 预览图片
        path = first.get("path") or ""
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(
                    400,
                    300,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.preview_label.setPixmap(pix)
            else:
                self.preview_label.setText("Preview not available")
        else:
            self.preview_label.setText("Preview not available")

        # 填充单条编辑表单（仅取第一条）
        date_str = first.get("date") or ""
        self.single_date_edit.setText(date_str)
        filt = first.get("filter_type") or first.get("filter") or ""
        if filt and filt in [f.value for f in FilterType]:
            idx = [f.value for f in FilterType].index(filt)
            self.single_filter_combo.setCurrentIndex(idx)

    def _open_selected_external(self) -> None:
        """用系统默认图片查看器打开第一个选中的快照。"""
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        path = selected[0].get("path")
        if not path:
            return
        url = QUrl.fromLocalFile(path)
        QDesktopServices.openUrl(url)

    def _apply_single_edit(self) -> None:
        """将右侧表单中的日期和滤镜应用到第一个选中的 snapshot。"""
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        snap_data = selected[0]
        snap_id = snap_data.get("id")
        if not snap_id:
            return

        # 解析日期
        date_text = self.single_date_edit.text().strip()
        try:
            gd = GameDate.fromiso(date_text)
        except Exception:
            return

        # 滤镜
        filt_value = self.single_filter_combo.currentText()
        try:
            filt = FilterType(filt_value)
        except Exception:
            filt = FilterType.CUSTOM

        camp = self._load_campaign()
        snap = self.storage.find_snapshot_by_id(camp, snap_id)
        if not snap:
            return

        snap.date = gd
        snap.filter_type = filt
        # 让 Campaign 内部快照按日期排序
        camp.snapshots.sort(key=lambda s: s.date.to_ordinal(False))
        self.storage.save_campaign(camp)
        self.refresh_snapshots()

    def _open_player(self) -> None:
        """打开当前存档的播放窗口。"""
        # StorageManager 把 campaign 建在 base_dir/Campaigns 下，
        # 而 PlayerWindow 期望传入的是根目录（即包含 Campaigns 的目录）
        base_root = self.storage.base_dir.parent
        player = PlayerWindow(
            self.campaign_name,
            storage_base_dir=base_root,
            parent=None,
        )
        player.show()

    def _apply_bulk_filter(self) -> None:
        """将选中快照的滤镜统一设置为下拉框选择的值。"""
        selected = self._selected_snapshot_dicts()
        if not selected:
            return
        filt_value = self.bulk_filter_combo.currentText()
        try:
            filt = FilterType(filt_value)
        except Exception:
            filt = FilterType.CUSTOM

        camp = self._load_campaign()
        id_to_data = {s.get("id"): s for s in selected if s.get("id")}
        for snap in camp.snapshots:
            if snap.id in id_to_data:
                snap.filter_type = filt

        self.storage.save_campaign(camp)
        self.refresh_snapshots()

    def _apply_bulk_date_offset(self) -> None:
        """对选中快照的日期施加偏移（正负 N 天/年）。"""
        selected = self._selected_snapshot_dicts()
        if not selected:
            return

        sign = 1 if self.bulk_sign_combo.currentText() == "+" else -1
        delta = self.bulk_delta_spin.value() * sign
        unit = self.bulk_unit_combo.currentText()

        camp = self._load_campaign()
        id_set = {s.get("id") for s in selected if s.get("id")}

        for snap in camp.snapshots:
            if snap.id not in id_set:
                continue
            if unit == "days":
                snap.date = snap.date.add_days(delta)
            else:  # years
                # 简单：只改年份，月份/日期保持，必要时由 GameDate 校验
                new_year = snap.date.year + delta
                try:
                    snap.date = GameDate(new_year, snap.date.month, snap.date.day)
                except Exception:
                    # 若目标日期非法（例如闰日），退一步用当月最后一天
                    import calendar

                    mdays = calendar.monthrange(new_year, snap.date.month)[1]
                    snap.date = GameDate(new_year, snap.date.month, mdays)

        camp.snapshots.sort(key=lambda s: s.date.to_ordinal(False))
        self.storage.save_campaign(camp)
        self.refresh_snapshots()
