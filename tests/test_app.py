"""主程序集成测试."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from src.app import App
from src.ocr.ocr_task import run_ocr_pipeline


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestApp(unittest.TestCase):
    """App 集成测试."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    @patch("src.app.TranslationCache")
    def test_init(self, mock_cache_cls) -> None:
        """测试 App 初始化会创建各模块实例."""
        app = App()
        app.init()

        self.assertIsNotNone(app.capture)
        self.assertIsNotNone(app.overlay)
        self.assertIsNotNone(app.translation_manager)
        self.assertIsNotNone(app.main_window)
        mock_cache_cls.assert_called_once()

    def test_ocr_pipeline_with_cache_hit(self) -> None:
        """测试 OCR 处理流程：OCR → 缓存命中 → 返回翻译项."""
        ocr_engine = MagicMock()
        translator = MagicMock()
        cache = MagicMock()

        ocr_engine.recognize = MagicMock(
            return_value=[
                {
                    "text": "こんにちは",
                    "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
                    "score": 0.95,
                }
            ]
        )
        translator.translate = MagicMock(return_value="你好")
        cache.get = MagicMock(return_value="你好")  # 缓存命中
        cache.set = MagicMock()

        image = Image.new("RGB", (100, 100))
        items = run_ocr_pipeline(
            image, 1.0, ocr_engine, translator, cache, "ja", "zh-CN"
        )

        ocr_engine.recognize.assert_called_once_with(image)
        cache.get.assert_called_once_with("こんにちは", "ja", "zh-CN")
        translator.translate.assert_not_called()  # 命中缓存不应调用翻译

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["translated"], "你好")
        self.assertEqual(items[0]["original"], "こんにちは")

    def test_ocr_pipeline_with_cache_miss(self) -> None:
        """测试 OCR 处理流程：OCR → 缓存未命中 → 翻译 → 写入缓存."""
        ocr_engine = MagicMock()
        translator = MagicMock()
        cache = MagicMock()

        ocr_engine.recognize = MagicMock(
            return_value=[
                {
                    "text": "こんにちは",
                    "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
                    "score": 0.95,
                }
            ]
        )
        translator.translate = MagicMock(return_value="你好")
        cache.get = MagicMock(return_value=None)  # 缓存未命中
        cache.set = MagicMock()

        image = Image.new("RGB", (100, 100))
        items = run_ocr_pipeline(
            image, 1.0, ocr_engine, translator, cache, "ja", "zh-CN"
        )

        translator.translate.assert_called_once_with("こんにちは", "ja", "zh-CN")
        cache.set.assert_called_once_with("こんにちは", "ja", "zh-CN", "你好")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["translated"], "你好")

    @patch("src.app.TranslationCache")
    @patch("src.app.TranslationProcessManager")
    @patch("src.app.CaptureThread")
    def test_start_stop(
        self,
        mock_capture_thread_cls,
        mock_manager_cls,
        mock_cache_cls,
    ) -> None:
        """测试启动和停止翻译循环会正确管理子进程与截图线程."""
        app = App()
        app.init()

        mock_manager = mock_manager_cls.return_value
        mock_capture_thread = mock_capture_thread_cls.return_value

        # 模拟已选择有效窗口
        app.capture.is_valid = MagicMock(return_value=True)
        app.capture.get_target = MagicMock(return_value=12345)
        app.overlay.show = MagicMock()
        app.overlay.hide = MagicMock()

        app.start()

        self.assertTrue(app.is_running)
        mock_manager.start.assert_called_once()
        mock_capture_thread_cls.assert_called_once()
        mock_capture_thread.start.assert_called_once()
        app.overlay.show.assert_called_once()

        app.stop()

        self.assertFalse(app.is_running)
        mock_capture_thread.stop.assert_called_once()
        mock_manager.stop.assert_called_once()
        app.overlay.hide.assert_called_once()

    @patch("src.app.TranslationCache")
    @patch("src.app.TranslationProcessManager")
    @patch("src.app.CaptureThread")
    def test_start_without_window(
        self,
        mock_capture_thread_cls,
        mock_manager_cls,
        mock_cache_cls,
    ) -> None:
        """测试未选择窗口且用户取消时不会启动任何后台组件."""
        app = App()
        app.init()

        app.capture.is_valid = MagicMock(return_value=False)
        app.select_window = MagicMock(return_value=False)

        app.start()

        self.assertFalse(app.is_running)
        mock_manager_cls.return_value.start.assert_not_called()
        mock_capture_thread_cls.assert_not_called()

    @patch("src.app.TranslationCache")
    @patch("src.app.TranslationProcessManager")
    @patch("src.app.CaptureThread")
    def test_ocr_finished_updates_overlay(
        self,
        mock_capture_thread_cls,
        mock_manager_cls,
        mock_cache_cls,
    ) -> None:
        """测试子进程结果信号会更新覆盖层与主窗口."""
        app = App()
        app.init()

        app.capture.is_valid = MagicMock(return_value=True)
        app.capture.get_target = MagicMock(return_value=12345)
        app.overlay.update_translations = MagicMock()
        app.main_window.update_recent = MagicMock()
        app.main_window.update_stats = MagicMock()
        app.main_window.update_performance = MagicMock()

        app.start()

        # 模拟子进程返回结果
        manager = mock_manager_cls.return_value
        finish_slot = manager.finished.connect.call_args[0][0]
        finish_slot(
            [
                {
                    "original": "こんにちは",
                    "translated": "你好",
                    "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
                    "score": 0.95,
                }
            ],
            0.5,
        )

        app.overlay.update_translations.assert_called_once()
        app.main_window.update_recent.assert_called_once()
        app.main_window.update_performance.assert_called_once()

    def _process_events(self, timeout_ms: int = 100) -> None:
        """处理当前线程的 Qt 事件，直到超时或队列为空."""
        loop = QEventLoop()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()


if __name__ == "__main__":
    unittest.main()
