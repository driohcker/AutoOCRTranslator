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


class TestCaptureThread(unittest.TestCase):
    """测试 CaptureThread 的截图与任务提交行为."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def _wait_for_signal(self, signal, timeout_ms: int = 500):
        """等待某个信号发出或超时."""
        loop = QEventLoop()
        signal.connect(loop.quit)
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    def _make_config_mock(self, preset="subtitle", max_width=480, roi_zones=None):
        config_mock = MagicMock()

        def config_get(key, default=None):
            values = {
                "ocr.roi_preset": preset,
                "ocr.roi_custom": [0.1, 0.75, 0.8, 0.2],
                "ocr.max_width": max_width,
                "ocr.roi_zones": roi_zones or [],
                "translate.source_lang": "ja",
                "translate.target_lang": "zh-CN",
                "translate.filter_source_lang": True,
                "translate.strict_source_lang": True,
            }
            return values.get(key, default)

        config_mock.get = config_get
        return config_mock

    @patch("src.capture.capture_thread.config")
    @patch("src.capture.capture_thread.WindowCapture")
    def test_capture_thread_submits_job(self, mock_capture_cls, mock_config):
        """测试截图线程会截图并提交翻译任务."""
        mock_config.get = self._make_config_mock().get
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        manager.is_busy.return_value = False

        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=5000)
        captured_images = []
        thread.frame_captured.connect(captured_images.append)
        thread.start()
        self._wait_for_signal(thread.frame_captured)
        thread.stop()

        manager.submit_job.assert_called()
        self.assertEqual(len(captured_images), 1)

        job = manager.submit_job.call_args[0][0]
        self.assertEqual(job["mode"], "single")
        self.assertEqual(len(job["zones"]), 1)

        # 200x200 * 0.8 宽度 = 160，未超过 max_width 480，保持原尺寸
        zone = job["zones"][0]
        self.assertEqual(zone["size"], (160, 40))

    @patch("src.capture.capture_thread.config")
    @patch("src.capture.capture_thread.WindowCapture")
    def test_capture_thread_skips_when_busy(self, mock_capture_cls, mock_config):
        """测试翻译子进程忙时截图线程会跳过."""
        mock_config.get = self._make_config_mock().get
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        manager.is_busy.return_value = True

        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=5000)
        thread.start()
        self._wait_for_signal(thread.frame_skipped)
        thread.stop()

        manager.submit_job.assert_not_called()

    @patch("src.capture.capture_thread.config")
    @patch("src.capture.capture_thread.WindowCapture")
    def test_capture_thread_window_invalid(self, mock_capture_cls, mock_config):
        """测试目标窗口无效时截图线程会发出信号."""
        mock_config.get = self._make_config_mock().get
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = False

        manager = MagicMock()
        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=5000)
        thread.start()
        self._wait_for_signal(thread.window_invalid)
        thread.stop()

        manager.submit_job.assert_not_called()

    @patch("src.capture.capture_thread.config")
    @patch("src.capture.capture_thread.WindowCapture")
    def test_capture_thread_custom_zones(self, mock_capture_cls, mock_config):
        """测试 custom_zones 模式会提交多区域任务."""
        mock_config.get = self._make_config_mock(
            preset="custom_zones",
            roi_zones=[
                [0.0, 0.0, 0.5, 0.5],
                [0.5, 0.5, 0.5, 0.5],
            ],
        ).get
        mock_capture = mock_capture_cls.return_value
        mock_capture.is_valid.return_value = True
        mock_capture.capture.return_value = Image.new("RGB", (200, 200))

        manager = MagicMock()
        manager.is_busy.return_value = False

        thread = CaptureThread(hwnd=12345, manager=manager, interval_ms=5000)
        thread.start()
        self._wait_for_signal(thread.frame_captured)
        thread.stop()

        manager.submit_job.assert_called()
        job = manager.submit_job.call_args[0][0]
        self.assertEqual(job["mode"], "multi_zone")
        self.assertEqual(len(job["zones"]), 2)


if __name__ == "__main__":
    unittest.main()
