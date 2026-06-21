"""区域选择器单元测试."""

import sys
import unittest

from PIL import Image
from PyQt6.QtWidgets import QApplication

from src.gui.zone_selector import ZoneSelector


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestZoneSelector(unittest.TestCase):
    """测试 ZoneSelector 坐标转换."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def test_zone_to_rect_with_qpoint(self):
        """使用真实 QPoint 测试坐标转换."""
        from PyQt6.QtCore import QPoint

        image = Image.new("RGB", (200, 100))
        screen_rect = (100, 50, 300, 150)
        selector = ZoneSelector(image, screen_rect)

        zone = selector._rect_to_zone(QPoint(120, 60), QPoint(220, 110))
        self.assertIsNotNone(zone)
        x, y, w, h = zone
        self.assertAlmostEqual(x, 0.1, places=5)
        self.assertAlmostEqual(y, 0.1, places=5)
        self.assertAlmostEqual(w, 0.5, places=5)
        self.assertAlmostEqual(h, 0.5, places=5)

        rect = selector._zone_to_rect(zone)
        # 注意 QRect.right() 是包含边界，验证时使用 left/top + width/height
        self.assertEqual(rect.left(), 120)
        self.assertEqual(rect.top(), 60)
        self.assertEqual(rect.left() + rect.width(), 220)
        self.assertEqual(rect.top() + rect.height(), 110)

    def test_rect_to_zone_clamped_to_screen(self):
        """测试拖拽超出目标窗口时会被限制在窗口内."""
        from PyQt6.QtCore import QPoint

        image = Image.new("RGB", (200, 100))
        screen_rect = (100, 50, 300, 150)
        selector = ZoneSelector(image, screen_rect)

        # 拖拽范围超出目标窗口
        zone = selector._rect_to_zone(QPoint(50, 30), QPoint(350, 180))
        x, y, w, h = zone
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertAlmostEqual(y, 0.0, places=5)
        self.assertAlmostEqual(w, 1.0, places=5)
        self.assertAlmostEqual(h, 1.0, places=5)

    def test_clear_all_then_done_returns_empty_zones(self):
        """测试清空所有区域后完成应返回空列表."""
        image = Image.new("RGB", (200, 100))
        screen_rect = (100, 50, 300, 150)
        selector = ZoneSelector(
            image,
            screen_rect,
            existing_zones=[(0.1, 0.2, 0.3, 0.4), (0.5, 0.6, 0.2, 0.1)],
        )

        self.assertEqual(len(selector._zones), 2)
        selector._clear_all()
        self.assertEqual(len(selector._zones), 0)

        selector._on_done()
        self.assertEqual(selector._result, [])


if __name__ == "__main__":
    unittest.main()
