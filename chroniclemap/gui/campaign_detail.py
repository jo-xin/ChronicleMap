from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chroniclemap.gui.campaign_store import CampaignStore
from chroniclemap.gui.import_widget import ImportWidget
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

        self.snapshot_list = QListWidget()
        layout.addWidget(self.snapshot_list, 1)

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
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.refresh_btn.clicked.connect(self.refresh_snapshots)
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
            text = f"{date} | {path}"
            item = QListWidgetItem(text)
            self.snapshot_list.addItem(item)
