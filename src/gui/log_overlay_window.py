"""悬浮日志窗口.

提供半透明、置顶、可拖动、可调整大小的悬浮日志窗口，
方便在全屏游戏或视频播放时查看调试日志，无需切换回主窗口.
"""

import logging
from typing import Any, Optional

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPalette
from PyQt6.QtWidgets import QMainWindow, QMenu, QTextEdit, QVBoxLayout, QWidget

from src.config import config

logger = logging.getLogger(__name__)


class LogOverlayWindow(QMainWindow):
    """半透明置顶悬浮日志窗口."""

    log_signal = pyqtSignal(str)

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._setup_window()
        self._setup_ui()
        self._setup_styles()
        self._setup_context_menu()
        self.load_geometry()

        self.log_signal.connect(self.append_log)

        # 拖动/调整大小状态
        self._dragging = False
        self._drag_pos = None
        self._resizing = False
        self._resize_pos = None
        self._resize_start_geometry = None

    def _setup_window(self) -> None:
        """设置窗口属性."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        opacity = config.get("log_overlay.opacity", 0.85)
        self.setWindowOpacity(opacity)

    def _setup_ui(self) -> None:
        """设置界面."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.log_text.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.log_text.customContextMenuRequested.connect(
            self._show_context_menu
        )
        layout.addWidget(self.log_text)

    def _setup_styles(self) -> None:
        """设置半透明样式."""
        font_size = config.get("log_overlay.font_size", 12)

        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: rgba(0, 0, 0, 180);
                border: 1px solid rgba(255, 255, 255, 100);
            }}
            QTextEdit {{
                background-color: rgba(0, 0, 0, 0);
                color: #00FF00;
                border: none;
                font-family: Consolas, Monaco, monospace;
                font-size: {font_size}px;
                padding: 4px;
            }}
            """
        )

        palette = self.log_text.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        self.log_text.setPalette(palette)

    def _setup_context_menu(self) -> None:
        """设置右键菜单."""
        self._context_menu = QMenu(self)
        self._action_clear = self._context_menu.addAction("清空日志")
        self._action_top = self._context_menu.addAction("取消置顶")
        self._action_top.setCheckable(True)
        self._action_top.setChecked(True)
        self._action_close = self._context_menu.addAction("关闭")

        self._action_clear.triggered.connect(self.clear_log)
        self._action_top.triggered.connect(self._toggle_topmost)
        self._action_close.triggered.connect(self.close)

    def _show_context_menu(self, pos: Any) -> None:
        """显示右键菜单."""
        self._context_menu.exec(self.log_text.mapToGlobal(pos))

    def _toggle_topmost(self) -> None:
        """切换置顶状态."""
        current_flags = self.windowFlags()
        if current_flags & Qt.WindowType.WindowStaysOnTopHint:
            self.setWindowFlags(
                current_flags & ~Qt.WindowType.WindowStaysOnTopHint
            )
            self._action_top.setText("置顶")
        else:
            self.setWindowFlags(
                current_flags | Qt.WindowType.WindowStaysOnTopHint
            )
            self._action_top.setText("取消置顶")
        self.show()

    def append_log(self, message: str) -> None:
        """追加日志."""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self) -> None:
        """清空日志."""
        self.log_text.clear()

    def load_geometry(self) -> None:
        """从配置加载位置和大小."""
        x = config.get("log_overlay.x", 1000)
        y = config.get("log_overlay.y", 100)
        width = config.get("log_overlay.width", 420)
        height = config.get("log_overlay.height", 320)
        self.setGeometry(x, y, width, height)

    def save_geometry(self) -> None:
        """保存位置和大小到配置."""
        geometry = self.geometry()
        config.set("log_overlay.x", geometry.x())
        config.set("log_overlay.y", geometry.y())
        config.set("log_overlay.width", geometry.width())
        config.set("log_overlay.height", geometry.height())
        config.save()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下：记录拖动或调整大小起始位置."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            rect = self.geometry()
            # 右下角 20x20 区域用于调整大小
            if (
                pos.x() >= rect.right() - 20
                and pos.y() >= rect.bottom() - 20
            ):
                self._resizing = True
                self._resize_pos = pos
                self._resize_start_geometry = rect
            else:
                self._dragging = True
                self._drag_pos = pos - rect.topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动：拖动窗口或调整大小."""
        pos = event.globalPosition().toPoint()
        if self._dragging:
            self.move(pos - self._drag_pos)
            event.accept()
        elif self._resizing:
            new_width = max(
                200,
                self._resize_start_geometry.width()
                + (pos.x() - self._resize_pos.x()),
            )
            new_height = max(
                150,
                self._resize_start_geometry.height()
                + (pos.y() - self._resize_pos.y()),
            )
            self.resize(new_width, new_height)
            event.accept()
        else:
            rect = self.geometry()
            if (
                pos.x() >= rect.right() - 20
                and pos.y() >= rect.bottom() - 20
            ):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放：结束拖动或调整大小."""
        self._dragging = False
        self._resizing = False
        self._drag_pos = None
        self._resize_pos = None
        self._resize_start_geometry = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.save_geometry()
        event.accept()

    def closeEvent(self, event: QEvent) -> None:
        """关闭时保存位置."""
        self.save_geometry()
        event.accept()


class LogOverlayHandler(logging.Handler):
    """将日志发送到悬浮日志窗口的处理器."""

    def __init__(self, window: LogOverlayWindow):
        super().__init__()
        self.window = window

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # 信号会自动排队到窗口所在线程（主线程）
            self.window.log_signal.emit(msg)
        except Exception:
            self.handleError(record)
