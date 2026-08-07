"""翻译子进程管理器测试."""

import queue as queue_module
import sys
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from src.worker.translation_manager import TranslationProcessManager


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestTranslationProcessManager(unittest.TestCase):
    """测试 TranslationProcessManager 生命周期与信号."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def _process_events(self, timeout_ms: int = 200) -> None:
        loop = QEventLoop()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    @patch("src.worker.translation_manager.multiprocessing.Queue", side_effect=queue_module.Queue)
    @patch("src.worker.translation_manager.multiprocessing.Process")
    def test_start_stop(self, mock_process_cls, _mock_queue):
        """测试管理器能启动和停止子进程."""
        mock_process = mock_process_cls.return_value
        mock_process.is_alive.return_value = False

        manager = TranslationProcessManager()
        config_dict = {"ocr": {"engine": "rapid"}}
        manager.start(config_dict)

        mock_process_cls.assert_called_once()
        mock_process.start.assert_called_once()

        manager.stop()

        mock_process.join.assert_not_called()
        mock_process.terminate.assert_not_called()
        self.assertIsNone(manager._process)

    @patch("src.worker.translation_manager.multiprocessing.Queue", side_effect=queue_module.Queue)
    @patch("src.worker.translation_manager.multiprocessing.Process")
    def test_submit_translation_job_and_receive_result(
        self, mock_process_cls, _mock_queue
    ):
        """测试提交任务后能从输出队列收到 translation_finished 信号."""
        mock_process = mock_process_cls.return_value
        mock_process.is_alive.return_value = False

        manager = TranslationProcessManager()
        config_dict = {"ocr": {"engine": "rapid"}}
        manager.start(config_dict)

        finished_args = []
        manager.translation_finished.connect(finished_args.append)

        job_id = manager.submit_translation_job(
            epoch=3,
            items=[{"id": 0, "text": "hello"}],
            source_lang="en",
            target_lang="zh-CN",
        )
        self.assertGreater(job_id, 0)

        # 手动注入子进程结果
        manager._output_queue.put(
            {
                "status": "finished",
                "job_id": job_id,
                "epoch": 3,
                "translations": [
                    {"id": 0, "original": "hello", "translated": "你好"}
                ],
                "elapsed": 0.3,
            }
        )
        self._process_events(300)

        self.assertEqual(len(finished_args), 1)
        result = finished_args[0]
        self.assertEqual(result["epoch"], 3)
        self.assertEqual(len(result["translations"]), 1)

        manager.stop()

    @patch("src.worker.translation_manager.multiprocessing.Queue", side_effect=queue_module.Queue)
    @patch("src.worker.translation_manager.multiprocessing.Process")
    def test_error_signal(self, mock_process_cls, _mock_queue):
        """测试子进程错误结果会触发 error 信号."""
        mock_process = mock_process_cls.return_value
        mock_process.is_alive.return_value = False

        manager = TranslationProcessManager()
        manager.start({"ocr": {"engine": "rapid"}})

        error_messages = []
        manager.error.connect(error_messages.append)

        manager.submit_translation_job(
            epoch=1,
            items=[{"id": 0, "text": "hello"}],
            source_lang="en",
            target_lang="zh-CN",
        )
        manager._output_queue.put({"status": "error", "error": "网络超时"})
        self._process_events(300)

        self.assertEqual(error_messages, ["网络超时"])

        manager.stop()


if __name__ == "__main__":
    unittest.main()
