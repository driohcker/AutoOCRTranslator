"""翻译子进程工作逻辑测试."""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtWidgets import QApplication

from src.worker.translation_worker import (
    _decode_image,
    _encode_image,
    _ensure_ocr_for_preset,
    _process_job,
    run_translation_worker,
)


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_image_bytes(size=(100, 40)):
    image = Image.new("RGB", size, color=(128, 128, 128))
    return {
        "bytes": image.tobytes(),
        "mode": image.mode,
        "size": image.size,
        "offset": (0, 0),
        "scale_ratio": 1.0,
    }


class TestTranslationWorker(unittest.TestCase):
    """测试 translation_worker 内部函数."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def test_decode_and_encode_image(self):
        """测试图像字节编解码."""
        image = Image.new("RGB", (80, 30), color="red")
        encoded = {
            "bytes": image.tobytes(),
            "mode": image.mode,
            "size": image.size,
        }
        decoded = _decode_image(encoded)
        self.assertEqual(decoded.size, image.size)
        self.assertEqual(decoded.mode, image.mode)

        png_bytes = _encode_image(decoded)
        self.assertTrue(len(png_bytes) > 0)
        restored = Image.open(io.BytesIO(png_bytes))
        self.assertEqual(restored.size, image.size)

    @patch("src.worker.translation_worker.run_ocr_pipeline")
    def test_process_job_single_zone(self, mock_pipeline):
        """测试单区域任务能返回正确结果."""
        mock_pipeline.return_value = [
            {
                "original": "hello",
                "translated": "你好",
                "box": [(10, 10), (50, 10), (50, 30), (10, 30)],
                "score": 0.95,
            }
        ]

        ocr = MagicMock()
        translator = MagicMock()
        cache = MagicMock()
        config_dict = {"ocr": {"engine": "rapid", "lang": "japan"}}
        job = {
            "preset": "subtitle",
            "zones": [_make_image_bytes()],
            "source_lang": "en",
            "target_lang": "zh-CN",
            "filter_source_lang": False,
            "strict_source_lang": False,
        }

        new_ocr, new_preset, result = _process_job(
            job, ocr, translator, cache, "subtitle", config_dict
        )

        self.assertEqual(new_ocr, ocr)
        self.assertEqual(new_preset, "subtitle")
        self.assertEqual(result["status"], "finished")
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("elapsed", result)
        self.assertIn("debug_image_bytes", result)
        self.assertIsInstance(result["debug_image_bytes"], list)
        self.assertEqual(len(result["debug_image_bytes"]), 1)

    @patch("src.worker.translation_worker.run_ocr_pipeline")
    def test_process_job_multi_zone(self, mock_pipeline):
        """测试多区域任务会合并结果."""
        mock_pipeline.side_effect = [
            [{"original": "a", "translated": "A", "box": [], "score": 0.9}],
            [{"original": "b", "translated": "B", "box": [], "score": 0.9}],
        ]

        ocr = MagicMock()
        translator = MagicMock()
        cache = MagicMock()
        config_dict = {"ocr": {"engine": "rapid", "lang": "japan"}}
        job = {
            "preset": "custom_zones",
            "zones": [_make_image_bytes(), _make_image_bytes()],
            "source_lang": "en",
            "target_lang": "zh-CN",
            "filter_source_lang": False,
            "strict_source_lang": False,
        }

        new_ocr, new_preset, result = _process_job(
            job, ocr, translator, cache, "subtitle", config_dict
        )

        self.assertEqual(result["status"], "finished")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(mock_pipeline.call_count, 2)

    def test_process_job_error(self):
        """测试 OCR 异常会被捕获并返回错误结果."""
        ocr = MagicMock()
        ocr.recognize.side_effect = RuntimeError("OCR 失败")
        translator = MagicMock()
        cache = MagicMock()
        config_dict = {"ocr": {"engine": "rapid", "lang": "japan"}}
        job = {
            "preset": "subtitle",
            "zones": [_make_image_bytes()],
            "source_lang": "en",
            "target_lang": "zh-CN",
        }

        new_ocr, new_preset, result = _process_job(
            job, ocr, translator, cache, "subtitle", config_dict
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("OCR 失败", result["error"])

    @patch("src.worker.translation_worker.create_ocr_engine")
    def test_ensure_ocr_for_preset(self, mock_create_engine):
        """测试 preset 变化时会重新初始化 OCR 引擎."""
        mock_create_engine.return_value = MagicMock()
        config_dict = {"ocr": {"engine": "rapid", "lang": "japan"}}

        ocr = MagicMock()
        new_ocr = _ensure_ocr_for_preset(ocr, "subtitle", "full", config_dict)
        mock_create_engine.assert_called_once()
        self.assertNotEqual(new_ocr, ocr)

        # 相同 preset 不重新初始化
        mock_create_engine.reset_mock()
        same_ocr = _ensure_ocr_for_preset(new_ocr, "full", "full", config_dict)
        mock_create_engine.assert_not_called()
        self.assertEqual(same_ocr, new_ocr)

    @patch("src.worker.translation_worker.run_ocr_pipeline")
    @patch("src.worker.translation_worker._init_modules")
    def test_run_translation_worker_loop(
        self, mock_init_modules, mock_pipeline
    ):
        """测试 worker 主循环处理任务并响应关闭信号."""
        mock_pipeline.return_value = []
        ocr = MagicMock()
        translator = MagicMock()
        cache = MagicMock()
        mock_init_modules.return_value = (ocr, translator, cache)

        import multiprocessing

        input_queue = multiprocessing.Queue()
        output_queue = multiprocessing.Queue()
        config_dict = {"ocr": {"engine": "rapid", "lang": "japan"}}

        job = {
            "preset": "subtitle",
            "zones": [_make_image_bytes()],
            "source_lang": "en",
            "target_lang": "zh-CN",
        }
        input_queue.put(job)
        input_queue.put(None)

        run_translation_worker(input_queue, output_queue, config_dict)

        # 输出队列中应有一个结果
        result = output_queue.get(timeout=1.0)
        self.assertEqual(result["status"], "finished")


if __name__ == "__main__":
    unittest.main()
