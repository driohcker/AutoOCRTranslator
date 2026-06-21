"""窗口捕获模块.

提供 Windows 窗口枚举、选择、客户区截图功能.
"""

import logging
from typing import List, Optional, Tuple

import mss
from PIL import Image
import win32gui

logger = logging.getLogger(__name__)


WindowInfo = Tuple[int, str]
"""窗口信息元组 (hwnd, title)."""


class WindowCaptureError(Exception):
    """窗口捕获相关异常."""

    pass


class WindowCapture:
    """Windows 窗口捕获器.

    负责枚举窗口、按关键词查找窗口、截取目标窗口客户区画面.
    """

    def __init__(self):
        self._hwnd: Optional[int] = None
        self._sct = mss.MSS()

    def __del__(self):
        """释放 mss 资源."""
        try:
            self._sct.close()
        except Exception:
            pass

    @staticmethod
    def list_windows(
        only_visible: bool = True, skip_empty_title: bool = True
    ) -> List[WindowInfo]:
        """枚举当前系统中的窗口.

        Args:
            only_visible: 是否只返回可见窗口. 默认 True.
            skip_empty_title: 是否跳过标题为空的窗口. 默认 True.

        Returns:
            窗口信息列表, 每项为 (hwnd, title).
        """
        windows: List[WindowInfo] = []

        def enum_callback(hwnd: int, _extra) -> None:
            if only_visible and not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if skip_empty_title and not title.strip():
                return
            windows.append((hwnd, title))

        win32gui.EnumWindows(enum_callback, None)
        return windows

    def find_window(self, keyword: str) -> Optional[WindowInfo]:
        """根据标题关键词查找第一个匹配的可见窗口.

        Args:
            keyword: 窗口标题关键词, 不区分大小写.

        Returns:
            匹配的窗口信息 (hwnd, title), 未找到返回 None.
        """
        keyword_lower = keyword.lower()
        windows = self.list_windows()
        for hwnd, title in windows:
            if keyword_lower in title.lower():
                return hwnd, title
        return None

    def set_target(self, hwnd: int) -> None:
        """设置目标窗口.

        Args:
            hwnd: 窗口句柄.

        Raises:
            WindowCaptureError: 当窗口句柄无效时.
        """
        if not win32gui.IsWindow(hwnd):
            raise WindowCaptureError(f"无效的窗口句柄: {hwnd}")
        self._hwnd = hwnd

    def get_target(self) -> Optional[int]:
        """获取当前目标窗口句柄."""
        return self._hwnd

    def is_valid(self) -> bool:
        """检查当前目标窗口是否仍然有效."""
        if self._hwnd is None:
            return False
        return bool(win32gui.IsWindow(self._hwnd))

    def get_client_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """获取目标窗口客户区在屏幕上的坐标.

        Returns:
            (left, top, right, bottom) 或窗口无效时返回 None.
        """
        if not self.is_valid():
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
            left, top = win32gui.ClientToScreen(self._hwnd, (left, top))
            right, bottom = win32gui.ClientToScreen(self._hwnd, (right, bottom))
            return left, top, right, bottom
        except Exception as e:
            logger.warning(f"获取窗口客户区坐标失败: {e}")
            return None

    def capture(self) -> Optional[Image.Image]:
        """截取目标窗口客户区画面.

        Returns:
            PIL.Image 对象, 窗口无效或截图失败时返回 None.
        """
        if not self.is_valid():
            logger.warning("目标窗口无效, 跳过本次截图")
            return None

        rect = self.get_client_rect()
        if rect is None:
            return None

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            logger.warning(f"窗口尺寸异常: width={width}, height={height}")
            return None

        try:
            monitor = {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
            sct_img = self._sct.grab(monitor)
            img = Image.frombytes(
                "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
            )
            return img
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return None


def select_window_dialog(
    windows: List[WindowInfo], parent=None
) -> Optional[int]:
    """弹出窗口选择对话框, 让用户手动选择目标窗口.

    Args:
        windows: 窗口信息列表.
        parent: 父窗口对象, 可选.

    Returns:
        用户选择的窗口句柄 hwnd, 取消或未选择返回 None.
    """
    if not windows:
        return None

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QDialog,
        QListWidget,
        QPushButton,
        QVBoxLayout,
    )

    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication([])
        created_app = True

    dialog = QDialog(parent)
    dialog.setWindowTitle("选择要翻译的游戏窗口")
    dialog.resize(500, 400)

    layout = QVBoxLayout(dialog)

    list_widget = QListWidget()
    for hwnd, title in windows:
        display = f"{title}  (hwnd: {hwnd})"
        list_widget.addItem(display)
        item = list_widget.item(list_widget.count() - 1)
        item.setData(Qt.ItemDataRole.UserRole, hwnd)

    layout.addWidget(list_widget)

    btn_ok = QPushButton("确定")
    layout.addWidget(btn_ok)

    selected_hwnd: Optional[int] = None

    def on_accept() -> None:
        nonlocal selected_hwnd
        item = list_widget.currentItem()
        if item is not None:
            selected_hwnd = item.data(Qt.ItemDataRole.UserRole)
        dialog.accept()

    btn_ok.clicked.connect(on_accept)
    list_widget.itemDoubleClicked.connect(on_accept)

    dialog.exec()

    if created_app:
        app.quit()

    return selected_hwnd
