"""窗口捕获模块.

提供 Windows 窗口枚举、选择、客户区截图功能。
截图使用 pywin32 原生 BitBlt（GetWindowDC + CreateDIBSection），
避免 mss 在 PyInstaller 冻结环境下的 DIB 内存读取噪声问题。
"""

import logging
from typing import List, Optional, Tuple

import win32gui
import win32ui
import win32con
from PIL import Image

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
            return self._bitblt_capture(left, top, width, height)
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return None

    @staticmethod
    def _bitblt_capture(
        left: int, top: int, width: int, height: int
    ) -> Image.Image:
        """用 pywin32 原生 BitBlt 截取屏幕区域.

        从屏幕 DC 直接拷贝像素到内存 DIB，与 mss 相比在 PyInstaller
        冻结环境下更稳定（mss 10.2 的 CreateDIBSection 实现打包后有
        内存读取噪声问题）。
        """
        # 屏幕 DC（目标窗口可能被其他窗口遮挡，屏幕 DC 能截到当前可见画面）
        screen_dc_handle = win32gui.GetDC(0)
        mem_dc = None
        bmp = None
        try:
            screen_dc = win32ui.CreateDCFromHandle(screen_dc_handle)
            mem_dc = screen_dc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(screen_dc, width, height)
            mem_dc.SelectObject(bmp)
            mem_dc.BitBlt((0, 0), (width, height), screen_dc, (left, top), win32con.SRCCOPY)
            info = bmp.GetInfo()
            bits = bmp.GetBitmapBits(True)
            return Image.frombuffer(
                "RGB",
                (info["bmWidth"], info["bmHeight"]),
                bits,
                "raw",
                "BGRX",
                0,
                1,
            )
        finally:
            if bmp is not None:
                win32gui.DeleteObject(bmp.GetHandle())
            if mem_dc is not None:
                mem_dc.DeleteDC()
            win32gui.ReleaseDC(0, screen_dc_handle)


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
