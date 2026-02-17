# chroniclemap/ui/widgets/canvas_view.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap  # 确保导入 QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class CanvasView(QGraphicsView):
    """
    Simple QGraphicsView wrapper that keeps a single QGraphicsPixmapItem.
    Provides set_image(path) to replace pixmap. Centers and fits preserving aspect ratio.
    Designed to be lightweight but easily extendable (layers, transforms).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 修复：使用正确的 RenderHint 类型
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 或者：self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self._current_path: Optional[str] = None

    def set_image(self, path: Optional[str], fit: bool = True):
        """
        Set image by filesystem path. If path is None, clear the scene.
        Only reloads if path changed.
        """
        if path is None:
            self._scene.clear()
            self._pix_item = None
            self._current_path = None
            return

        if self._current_path == path and self._pix_item is not None:
            # no change
            if fit:
                self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)
            return

        # load new pixmap
        pix = QPixmap(path)
        if pix.isNull():
            # clear on failure
            self._scene.clear()
            self._pix_item = None
            self._current_path = None
            return

        # clear scene and add pixmap
        self._scene.clear()
        item = QGraphicsPixmapItem(pix)
        # 修复：使用正确的枚举（PySide6 需要显式命名空间）
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(item)
        self._pix_item = item
        self._current_path = path

        if fit:
            self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # ensure current image remains fitted on resize
        if self._pix_item is not None:
            self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)
