"""主窗口 UI 测试."""

import sys
import unittest
from unittest.mock import MagicMock

from PIL import Image
from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestMainWindow(unittest.TestCase):
    """测试 MainWindow 的 OCR 预览功能."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def _create_window(self):
        controller = MagicMock()
        controller.is_running = False
        return MainWindow(controller)

    def test_ocr_preview_accepts_single_image(self):
        """单张图像也能正常显示."""
        window = self._create_window()
        image = Image.new("RGB", (120, 80), color="red")

        window.set_ocr_preview(image)

        self.assertEqual(len(window._ocr_preview_images), 1)
        window.close()

    def test_ocr_preview_displays_multiple_images(self):
        """多张图像以网格形式显示."""
        window = self._create_window()
        images = [Image.new("RGB", (80, 60), color="green") for _ in range(3)]

        window.set_ocr_preview(images)

        self.assertEqual(len(window._ocr_preview_images), 3)
        widgets = [
            window.ocr_preview_layout.itemAt(i).widget()
            for i in range(window.ocr_preview_layout.count())
        ]
        self.assertEqual(len(widgets), 3)
        window.close()

    def test_ocr_preview_new_batch_replaces_old(self):
        """新的识别批次会替换掉旧的预览."""
        window = self._create_window()
        window.set_ocr_preview(
            [Image.new("RGB", (80, 60), color="red") for _ in range(4)]
        )
        window.set_ocr_preview(
            [Image.new("RGB", (80, 60), color="blue") for _ in range(2)]
        )

        self.assertEqual(len(window._ocr_preview_images), 2)
        widgets = [
            window.ocr_preview_layout.itemAt(i).widget()
            for i in range(window.ocr_preview_layout.count())
        ]
        self.assertEqual(len(widgets), 2)
        window.close()


if __name__ == "__main__":
    unittest.main()
