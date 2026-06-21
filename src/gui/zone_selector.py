"""区域划分选择器.

提供全屏半透明遮罩，允许用户通过鼠标拖拽在目标窗口截图上
划定一个或多个矩形区域，用于“自定义区域划分”ROI 模式.
"""

import logging
from typing import List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton

logger = logging.getLogger(__name__)

Zone = Tuple[float, float, float, float]
"""区域相对坐标 [x_ratio, y_ratio, w_ratio, h_ratio]，范围 0~1."""


class ZoneSelector(QDialog):
    """全屏区域拖拽选择器.

    使用示例:
        selector = ZoneSelector(background_image, screen_rect, parent)
        zones = selector.select()
        if zones is not None:
            ...
    """

    def __init__(
        self,
        background_image: Image.Image,
        screen_rect: Tuple[int, int, int, int],
        existing_zones: Optional[List[Zone]] = None,
        parent: Optional[QDialog] = None,
    ) -> None:
        """初始化选择器.

        Args:
            background_image: 目标窗口当前截图，用于在遮罩中央显示真实画面。
            screen_rect: 目标窗口在屏幕上的像素坐标 (left, top, right, bottom)。
            existing_zones: 已存在的区域列表，打开时直接显示。
            parent: 父窗口。
        """
        super().__init__(parent)

        self._bg_image = background_image
        # 使用独立的整数字段存储，避免 QRect 的包含边界语义导致坐标误差
        self._screen_left = screen_rect[0]
        self._screen_top = screen_rect[1]
        self._screen_width = screen_rect[2] - screen_rect[0]
        self._screen_height = screen_rect[3] - screen_rect[1]
        self._screen_rect = QRect(
            self._screen_left,
            self._screen_top,
            self._screen_width,
            self._screen_height,
        )
        self._zones: List[Zone] = list(existing_zones or [])
        self._result: Optional[List[Zone]] = None

        # 当前拖拽状态
        self._dragging = False
        self._drag_start = QPoint()
        self._drag_current = QPoint()

        # 转换为 QPixmap 用于绘制
        self._pixmap = self._pil_to_pixmap(background_image)

        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        """设置窗口属性."""
        self.setWindowTitle("划分翻译区域")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 覆盖主屏幕（多显示器场景下先简单处理）
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def _setup_ui(self) -> None:
        """创建底部提示与按钮."""
        self._hint_label = QLabel(self)
        self._hint_label.setText(
            "拖拽鼠标画区域 | Enter 完成 | Esc 取消 | Ctrl+Z 撤销 | Delete 清空"
        )
        self._hint_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,180); padding: 6px 12px;"
        )
        self._hint_label.setFont(QFont("Microsoft YaHei", 12))
        self._hint_label.adjustSize()

        self._btn_done = QPushButton("完成", self)
        self._btn_cancel = QPushButton("取消", self)
        self._btn_undo = QPushButton("撤销", self)
        self._btn_clear = QPushButton("清空", self)

        for btn in (self._btn_done, self._btn_cancel, self._btn_undo, self._btn_clear):
            btn.setStyleSheet(
                "QPushButton { background-color: rgba(50,50,50,220); color: white; "
                "border: 1px solid #888; padding: 6px 16px; font-size: 13px; }"
                "QPushButton:hover { background-color: rgba(80,80,80,240); }"
            )

        self._btn_done.clicked.connect(self._on_done)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_undo.clicked.connect(self._undo_last)
        self._btn_clear.clicked.connect(self._clear_all)

        self._layout_buttons()

    def _layout_buttons(self) -> None:
        """摆放底部按钮和提示文字."""
        margin = 20
        hint_w = self._hint_label.width()
        hint_h = self._hint_label.height()
        btn_h = self._btn_done.height()

        screen = self.geometry()
        y = screen.bottom() - margin - max(hint_h, btn_h)

        # 提示文字居中
        self._hint_label.move((screen.width() - hint_w) // 2, y)

        # 按钮放在提示文字右侧
        total_btn_w = sum(
            b.width() for b in (self._btn_done, self._btn_cancel, self._btn_undo, self._btn_clear)
        ) + 30  # 3 个间距
        start_x = (screen.width() + hint_w) // 2 + 20
        if start_x + total_btn_w > screen.width() - margin:
            # 如果右侧放不下，则把按钮放在提示文字下方居中
            start_x = (screen.width() - total_btn_w) // 2
            y += max(hint_h, btn_h) + 10

        x = start_x
        for btn in (self._btn_done, self._btn_undo, self._btn_clear, self._btn_cancel):
            btn.move(x, y)
            x += btn.width() + 10

    def _pil_to_pixmap(self, image: Image.Image) -> QPixmap:
        """将 PIL.Image 转换为 QPixmap."""
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        from PyQt6.QtGui import QImage
        qimage = QImage(
            data, image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888
        )
        return QPixmap.fromImage(qimage)

    def select(self) -> Optional[List[Zone]]:
        """模态显示选择器并等待用户操作.

        Returns:
            用户点击“完成”或按 Enter 时返回区域相对坐标列表；
            取消或按 Esc 时返回 None。
        """
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

        result = self.exec()
        logger.info(f"ZoneSelector exec 返回: {result}, _result={self._result}")

        return self._result

    def _on_done(self) -> None:
        """完成选择."""
        self._result = list(self._zones)
        logger.info(f"ZoneSelector 完成选择，返回 {len(self._result)} 个区域")
        self.accept()

    def _on_cancel(self) -> None:
        """取消选择."""
        self._result = None
        logger.info("ZoneSelector 取消选择")
        self.reject()

    def _undo_last(self) -> None:
        """撤销最后一个区域."""
        if self._zones:
            self._zones.pop()
            self.update()

    def _clear_all(self) -> None:
        """清空所有区域."""
        self._zones.clear()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """处理快捷键."""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self._on_cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_done()
        elif key == Qt.Key.Key_Z and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._undo_last()
        elif key == Qt.Key.Key_Delete:
            self._clear_all()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """开始拖拽绘制."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if self._screen_rect.contains(pos):
                self._dragging = True
                self._drag_start = pos
                self._drag_current = pos
                event.accept()
            else:
                event.ignore()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """更新拖拽矩形."""
        if self._dragging:
            self._drag_current = event.globalPosition().toPoint()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """结束拖拽并保存区域."""
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            end_pos = event.globalPosition().toPoint()
            zone = self._rect_to_zone(self._drag_start, end_pos)
            if zone is not None:
                self._zones.append(zone)
                logger.info(f"新增区域: {zone}")
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _rect_to_zone(
        self, p1: QPoint, p2: QPoint
    ) -> Optional[Zone]:
        """将屏幕坐标矩形转换为相对目标窗口的坐标."""
        left = min(p1.x(), p2.x())
        top = min(p1.y(), p2.y())
        right = max(p1.x(), p2.x())
        bottom = max(p1.y(), p2.y())

        # 限制在目标窗口范围内（使用独立字段避免 QRect 包含边界误差）
        right_excl = self._screen_left + self._screen_width
        bottom_excl = self._screen_top + self._screen_height
        left = max(left, self._screen_left)
        top = max(top, self._screen_top)
        right = min(right, right_excl)
        bottom = min(bottom, bottom_excl)

        if right <= left or bottom <= top:
            return None

        x_ratio = (left - self._screen_left) / self._screen_width
        y_ratio = (top - self._screen_top) / self._screen_height
        w_ratio = (right - left) / self._screen_width
        h_ratio = (bottom - top) / self._screen_height

        # 处理浮点精度
        x_ratio = max(0.0, min(1.0, x_ratio))
        y_ratio = max(0.0, min(1.0, y_ratio))
        w_ratio = max(0.0, min(1.0 - x_ratio, w_ratio))
        h_ratio = max(0.0, min(1.0 - y_ratio, h_ratio))

        if w_ratio <= 0 or h_ratio <= 0:
            return None

        return (x_ratio, y_ratio, w_ratio, h_ratio)

    def _zone_to_rect(self, zone: Zone) -> QRect:
        """将相对坐标转换为屏幕像素矩形."""
        x_ratio, y_ratio, w_ratio, h_ratio = zone
        left = self._screen_left + int(self._screen_width * x_ratio)
        top = self._screen_top + int(self._screen_height * y_ratio)
        right = left + int(self._screen_width * w_ratio)
        bottom = top + int(self._screen_height * h_ratio)
        return QRect(left, top, right - left, bottom - top)

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制遮罩、截图、已保存区域和拖拽中区域."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 全屏半透明黑色遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))

        # 绘制目标窗口截图（清晰区域）
        if not self._pixmap.isNull():
            painter.drawPixmap(self._screen_rect.topLeft(), self._pixmap)

        # 已保存区域：半透明绿色填充 + 边框
        fill_pen = QPen(QColor(0, 255, 0, 160))
        fill_brush = QBrush(QColor(0, 255, 0, 40))
        for zone in self._zones:
            rect = self._zone_to_rect(zone)
            painter.setPen(fill_pen)
            painter.setBrush(fill_brush)
            painter.drawRect(rect)

        # 当前拖拽中区域：半透明红色
        if self._dragging:
            rect = QRect(self._drag_start, self._drag_current).normalized()
            rect = rect.intersected(self._screen_rect)
            if rect.isValid():
                painter.setPen(QPen(QColor(255, 0, 0, 200)))
                painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
                painter.drawRect(rect)

        painter.end()
