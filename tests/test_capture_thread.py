"""截图线程测试."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from src.capture.capture_thread import CaptureThread


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_config_mock(preset="subtitle", max_width=480, roi_zones=None):
    config_mock = MagicMock()

    def config_get(key, default=None):
        values = {
            "ocr.roi_preset": preset,
            "ocr.roi_custom": [0.1, 0.75, 0.8, 0.2],
            "ocr.max_width": max_width,
            "ocr.roi_zones": roi_zones or [],
            "ocr.engine": "rapid",
            "ocr.lang": "japan",
            "ocr.use_gpu": False,
            "translate.source_lang": "ja",
            "translate.target_lang": "zh-CN",
            "translate.filter_source_lang": False,
            "translate.strict_source_lang": False,
        }
        return values.get(key, default)

    config_mock.get = config_get
    return config_mock


def _make_ocr_mock():
    """构造一个返回单个文本块的 mock OCR 引擎."""
    ocr = MagicMock()
    ocr.recognize.return_value = [
        {
            "text": "こんにちは",
            "box": [(10, 10), (100, 10), (100, 40), (10, 40)],
            "score": 0.95,
        }
    ]
    return ocr


class TestCaptureThread(unittest.TestCase):
    """测试 CaptureThread 的截图、变化检测与本地 OCR 行为."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def _wait_for_signal(self, signal, timeout_ms: int = 1000):
        """等待某个信号发出或超时."""
        loop = QEventLoop()
        signal.connect(loop.quit)
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    def _make_thread(self, manager, preset="subtitle", **kwargs):
        """构造线程并注入 mock OCR 引擎（不加载真实模型）."""
        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=50, **kwargs)
        # 直接注入 mock 引擎，绕过 create_ocr_engine（避免加载模型）
        thread._ocr_engine = _make_ocr_mock()
        thread._current_preset = preset
        return thread

    @patch("src.capture.capture_thread.WindowCapture")
    @patch("src.capture.capture_thread.config", _make_config_mock())
    def test_capture_thread_runs_ocr_and_submits_translation(
        self, mock_capture_cls
    ):
        """测试截图线程会截图、本地 OCR，并把未命中的文本提交翻译."""
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        thread = self._make_thread(manager)
        ocr_results = []
        thread.ocr_ready.connect(
            lambda epoch, items, elapsed: ocr_results.append((epoch, items))
        )
        thread.start()
        self._wait_for_signal(thread.ocr_ready)
        thread.stop()

        # 本地 OCR 完成信号
        self.assertEqual(len(ocr_results), 1)
        epoch, items = ocr_results[0]
        self.assertEqual(epoch, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["original"], "こんにちは")

        # 缓存未命中（cache=None）→ 提交纯文本翻译任务
        manager.submit_translation_job.assert_called()
        args = manager.submit_translation_job.call_args[0]
        self.assertEqual(args[0], epoch)
        self.assertEqual(len(args[1]), 1)
        self.assertEqual(args[1][0]["text"], "こんにちは")
        self.assertEqual(args[2], "ja")
        self.assertEqual(args[3], "zh-CN")

    @patch("src.capture.capture_thread.WindowCapture")
    @patch("src.capture.capture_thread.config", _make_config_mock())
    def test_capture_thread_skips_unchanged_frames(self, mock_capture_cls):
        """测试画面无变化时跳过 OCR（变化检测闸门）."""
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        thread = self._make_thread(manager)
        thread.start()
        self._wait_for_signal(thread.frame_skipped)
        thread.stop()

        # 连续相同画面：第一次触发 OCR，之后跳过 → 仅一次翻译提交
        manager.submit_translation_job.assert_called_once()
        self.assertGreaterEqual(thread._skipped_frames, 1)

    @patch("src.capture.capture_thread.WindowCapture")
    @patch("src.capture.capture_thread.config", _make_config_mock())
    def test_capture_thread_window_invalid(self, mock_capture_cls):
        """测试目标窗口无效时截图线程会发出信号."""
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = False

        manager = MagicMock()
        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=50)
        thread.start()
        self._wait_for_signal(thread.window_invalid)
        thread.stop()

        manager.submit_translation_job.assert_not_called()

    @patch("src.capture.capture_thread.WindowCapture")
    @patch(
        "src.capture.capture_thread.config",
        _make_config_mock(
            preset="custom_zones",
            roi_zones=[
                [0.0, 0.0, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5],
            ],
        ),
    )
    def test_capture_thread_custom_zones(self, mock_capture_cls):
        """测试 custom_zones 模式会合并多区域识别结果."""
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        thread = self._make_thread(manager, preset="custom_zones")
        ocr_results = []
        thread.ocr_ready.connect(
            lambda epoch, items, elapsed: ocr_results.append(items)
        )
        thread.start()
        self._wait_for_signal(thread.ocr_ready)
        thread.stop()

        # 两个区域各识别 1 个文本块，合并为 2 个
        self.assertEqual(len(ocr_results), 1)
        self.assertEqual(len(ocr_results[0]), 2)


if __name__ == "__main__":
    unittest.main()
