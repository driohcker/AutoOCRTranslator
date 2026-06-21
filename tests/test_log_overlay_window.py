"""悬浮日志窗口单元测试."""

import sys
import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.gui.log_overlay_window import LogOverlayWindow


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestLogOverlayWindow(unittest.TestCase):
    """测试悬浮日志窗口."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def test_window_flags(self):
        """测试窗口标志：无边框、置顶、工具窗口."""
        window = LogOverlayWindow()
        flags = window.windowFlags()
        self.assertTrue(
            bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        )
        self.assertTrue(bool(flags & Qt.WindowType.Tool))
        self.assertTrue(
            window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        )

    def test_append_log(self):
        """测试追加日志."""
        window = LogOverlayWindow()
        window.append_log("测试日志 1")
        window.append_log("测试日志 2")
        text = window.log_text.toPlainText()
        self.assertIn("测试日志 1", text)
        self.assertIn("测试日志 2", text)

    def test_clear_log(self):
        """测试清空日志."""
        window = LogOverlayWindow()
        window.append_log("测试日志")
        window.clear_log()
        self.assertEqual(window.log_text.toPlainText(), "")


if __name__ == "__main__":
    unittest.main()
