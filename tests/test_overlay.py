"""覆盖层模块测试."""

import unittest

from PyQt6.QtCore import Qt

from src.overlay.overlay_window import OverlayWindow, TranslationItem


def _ensure_app():
    """确保存在 QApplication 实例."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestOverlayWindow(unittest.TestCase):
    """OverlayWindow 单元测试."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def test_window_flags(self) -> None:
        """测试覆盖层窗口具有预期标志：无边框、置顶、工具窗口、点击穿透."""
        overlay = OverlayWindow()
        flags = overlay.windowFlags()

        self.assertTrue(
            flags & Qt.WindowType.FramelessWindowHint,
            "应启用无边框",
        )
        self.assertTrue(
            flags & Qt.WindowType.WindowStaysOnTopHint,
            "应启用置顶",
        )
        self.assertTrue(
            flags & Qt.WindowType.Tool,
            "应启用工具窗口",
        )
        self.assertTrue(
            flags & Qt.WindowType.WindowTransparentForInput,
            "应启用点击穿透",
        )

    def test_translucent_background(self) -> None:
        """测试覆盖层启用半透明背景."""
        overlay = OverlayWindow()
        self.assertTrue(
            overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        )

    def test_set_target_window(self) -> None:
        """测试设置目标窗口句柄."""
        overlay = OverlayWindow()
        overlay.set_target_window(12345)
        self.assertEqual(overlay._target_hwnd, 12345)

    def test_update_translations(self) -> None:
        """测试更新翻译项."""
        overlay = OverlayWindow()
        items: list[TranslationItem] = [
            {
                "original": "hello",
                "translated": "你好",
                "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
            }
        ]
        overlay.update_translations(items)
        self.assertEqual(len(overlay._translations), 1)
        self.assertEqual(overlay._translations[0]["translated"], "你好")

    def test_apply_style(self) -> None:
        """测试应用样式."""
        overlay = OverlayWindow()
        overlay.apply_style(
            font_family="SimSun",
            font_size=24,
            font_color="#FF0000",
            bg_color="#00FF00",
            border_color="#0000FF",
            max_width=300,
        )

        self.assertEqual(overlay._font_family, "SimSun")
        self.assertEqual(overlay._font_size, 24)
        self.assertEqual(overlay._font_color, "#FF0000")
        self.assertEqual(overlay._bg_color, "#00FF00")
        self.assertEqual(overlay._border_color, "#0000FF")
        self.assertEqual(overlay._max_width, 300)

    def test_paint_event_no_crash(self) -> None:
        """测试绘制事件不崩溃."""
        overlay = OverlayWindow()
        items: list[TranslationItem] = [
            {
                "original": "こんにちは",
                "translated": "你好",
                "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
            },
            {
                "original": "hello",
                "translated": "你好",
                "box": [],  # 无效 box，应被跳过
            },
        ]
        overlay.update_translations(items)

        # 触发一次 paintEvent
        try:
            overlay.show()
            overlay.repaint()
            overlay.hide()
        except Exception as e:
            self.fail(f"paintEvent 不应抛出异常: {e}")


if __name__ == "__main__":
    unittest.main()
