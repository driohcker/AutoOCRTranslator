"""覆盖层模块.

使用 PyQt6 创建无边框、置顶、透明、点击穿透的覆盖层窗口,
将译文显示在游戏画面原文字位置上方.
"""

import logging
from typing import Any, Dict, List, Optional

import win32gui
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)


TranslationItem = Dict[str, Any]
"""翻译项格式.

格式: {
    "original": str,
    "translated": str,
    "box": List[Tuple[int, int]],  # 四边形边界框
    ...
}
"""


class OverlayWindow(QWidget):
    """翻译覆盖层窗口."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """初始化覆盖层窗口."""
        super().__init__(parent)

        self._target_hwnd: Optional[int] = None
        self._translations: List[TranslationItem] = []
        self._zones: List[List[float]] = []

        # 默认样式
        self._font_family = "Microsoft YaHei"
        self._font_size = 18
        self._font_color = "#FFFFFF"
        self._bg_color = "#80000000"
        self._border_color = "#FF000000"
        self._max_width = 400

        # 窗口属性：无边框、置顶、工具窗口（不在任务栏显示）、点击穿透
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 定时器：跟随目标窗口位置变化
        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._follow_target_window)
        self._follow_timer.start(100)  # 100ms 刷新一次

    def set_target_window(self, hwnd: int) -> None:
        """设置要跟随的目标窗口句柄."""
        self._target_hwnd = hwnd

    def update_translations(self, items: List[TranslationItem]) -> None:
        """更新要显示的翻译项列表."""
        self._translations = items
        self.update()

    def set_zones(self, zones: List[List[float]]) -> None:
        """设置需要高亮显示的区域列表.

        Args:
            zones: 每个区域为 [x_ratio, y_ratio, w_ratio, h_ratio]。
        """
        self._zones = [list(z) for z in zones]
        self.update()

    def apply_style(
        self,
        font_family: Optional[str] = None,
        font_size: Optional[int] = None,
        font_color: Optional[str] = None,
        bg_color: Optional[str] = None,
        border_color: Optional[str] = None,
        max_width: Optional[int] = None,
    ) -> None:
        """应用显示样式."""
        if font_family is not None:
            self._font_family = font_family
        if font_size is not None:
            self._font_size = font_size
        if font_color is not None:
            self._font_color = font_color
        if bg_color is not None:
            self._bg_color = bg_color
        if border_color is not None:
            self._border_color = border_color
        if max_width is not None:
            self._max_width = max_width
        self.update()

    def _follow_target_window(self) -> None:
        """定时更新覆盖层窗口位置，使其与目标窗口客户区对齐."""
        if self._target_hwnd is None or not win32gui.IsWindow(self._target_hwnd):
            return

        try:
            left, top, right, bottom = win32gui.GetClientRect(self._target_hwnd)
            left, top = win32gui.ClientToScreen(self._target_hwnd, (left, top))
            right, bottom = win32gui.ClientToScreen(
                self._target_hwnd, (right, bottom)
            )

            width = right - left
            height = bottom - top

            self.setGeometry(left, top, width, height)
        except Exception as e:
            logger.warning(f"跟随目标窗口失败: {e}")

    def paintEvent(self, event: Any) -> None:
        """绘制译文覆盖层."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 先绘制自定义区域高亮（微微显示）
        self._draw_zones(painter)

        font = QFont(self._font_family, self._font_size)
        painter.setFont(font)

        pen_color = QColor(self._font_color)
        bg_color = QColor(self._bg_color)
        border_color = QColor(self._border_color)

        for item in self._translations:
            box = item.get("box", [])
            if len(box) < 4:
                continue

            text = item.get("translated", item.get("text", ""))
            if not text:
                continue

            # 使用边界框左上角作为文本起始位置
            x = box[0][0]
            y = box[0][1]

            # 计算文本需要的绘制区域
            text_rect = painter.boundingRect(
                x,
                y,
                self._max_width,
                1000,
                Qt.TextFlag.TextWordWrap,
                text,
            )

            # 绘制半透明背景框
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(border_color))
            painter.drawRoundedRect(text_rect, 4, 4)

            # 绘制译文文本
            painter.setPen(QPen(pen_color))
            painter.drawText(text_rect, Qt.TextFlag.TextWordWrap, text)

    def _draw_zones(self, painter: QPainter) -> None:
        """绘制自定义区域半透明高亮框."""
        if not self._zones:
            return

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        fill_color = QColor(255, 0, 0, 30)   # 很淡的红色填充
        border_color = QColor(255, 0, 0, 120)  # 半透明红色边框
        pen = QPen(border_color)
        pen.setWidth(2)
        brush = QBrush(fill_color)

        for zone in self._zones:
            if len(zone) != 4:
                continue
            x_ratio, y_ratio, w_ratio, h_ratio = zone
            x = int(width * x_ratio)
            y = int(height * y_ratio)
            w = int(width * w_ratio)
            h = int(height * h_ratio)
            if w <= 0 or h <= 0:
                continue

            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(x, y, w, h)
