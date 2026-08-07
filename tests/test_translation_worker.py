"""翻译子进程工作逻辑测试."""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtWidgets import QApplication

from src.worker.translation_worker import (
    _batch_translate,
    _process_job,
    run_translation_worker,
)


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_job(epoch=1, job_id=1):
    """构造一个纯文本翻译任务."""
    return {
        "job_id": job_id,
        "epoch": epoch,
        "items": [
            {"id": 0, "text": "hello"},
            {"id": 1, "text": "world"},
        ],
        "source_lang": "en",
        "target_lang": "zh-CN",
    }


class TestTranslationWorker(unittest.TestCase):
    """测试 translation_worker 内部函数."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def test_batch_translate_single(self):
        """单条文本直接翻译."""
        translator = MagicMock()
        translator.translate.return_value = "你好"
        result = _batch_translate(["hello"], translator, "en", "zh-CN")
        self.assertEqual(result, ["你好"])

    def test_batch_translate_multi(self):
        """多条文本合并为一次调用，条数匹配时直接拆分."""
        translator = MagicMock()
        translator.translate.return_value = "你好\n世界"
        result = _batch_translate(["hello", "world"], translator, "en", "zh-CN")
        self.assertEqual(result, ["你好", "世界"])
        self.assertEqual(translator.translate.call_count, 1)

    def test_batch_translate_mismatch_fallback(self):
        """条数不匹配时逐条回退."""
        translator = MagicMock()
        translator.translate.side_effect = ["你好\n世界\n多了一个"]
        result = _batch_translate(["hello", "world"], translator, "en", "zh-CN")
        # 回退逐条：3 次调用（首次合并 + 2 条回退）
        self.assertEqual(translator.translate.call_count, 3)
        self.assertEqual(len(result), 2)

    def test_batch_translate_failure_fallback_to_original(self):
        """翻译失败时以原文兜底."""
        translator = MagicMock()
        translator.translate.side_effect = RuntimeError("网络超时")
        result = _batch_translate(["hello"], translator, "en", "zh-CN")
        self.assertEqual(result, ["hello"])

    def test_process_job_cache_hit(self):
        """缓存命中的文本不调用翻译器."""
        translator = MagicMock()
        cache = MagicMock()
        cache.get.return_value = "你好"

        result = _process_job(_make_job(), translator, cache)

        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["epoch"], 1)
        self.assertEqual(result["job_id"], 1)
        self.assertEqual(len(result["translations"]), 2)
        translator.translate.assert_not_called()
        self.assertEqual(result["translations"][0]["translated"], "你好")

    def test_process_job_cache_miss_translates(self):
        """缓存未命中时批量翻译并写回缓存."""
        translator = MagicMock()
        translator.translate.return_value = "你好\n世界"
        cache = MagicMock()
        cache.get.return_value = None

        result = _process_job(_make_job(), translator, cache)

        self.assertEqual(result["status"], "finished")
        self.assertEqual(len(result["translations"]), 2)
        self.assertEqual(
            [t["translated"] for t in result["translations"]], ["你好", "世界"]
        )
        self.assertEqual(cache.set.call_count, 2)
        # 每项含 original 供主进程按文本合并
        self.assertEqual(result["translations"][0]["original"], "hello")

    def test_process_job_error(self):
        """翻译异常被捕获并返回错误结果."""
        translator = MagicMock()
        translator.translate.side_effect = RuntimeError("网络超时")
        cache = MagicMock()
        cache.get.return_value = None

        result = _process_job(_make_job(), translator, cache)

        # 失败兜底为原文，整体仍为 finished
        self.assertEqual(result["status"], "finished")
        self.assertEqual(
            [t["translated"] for t in result["translations"]], ["hello", "world"]
        )

    @patch("src.worker.translation_worker._init_translator")
    @patch("src.worker.translation_worker._init_cache")
    def test_run_translation_worker_loop(
        self, mock_init_cache, mock_init_translator
    ):
        """测试 worker 主循环：任务异步处理并响应关闭信号."""
        mock_translator = MagicMock()
        mock_translator.translate.return_value = "你好\n世界"
        mock_init_translator.return_value = mock_translator
        mock_init_cache.return_value = None

        import multiprocessing
        import time

        input_queue = multiprocessing.Queue()
        output_queue = multiprocessing.Queue()
        config_dict = {"translate": {"concurrency": 2}}

        input_queue.put(_make_job())
        input_queue.put(None)

        # 直接调用入口函数（进程内执行，线程池 + 回调均在当前进程内）
        run_translation_worker(input_queue, output_queue, config_dict)

        # 异步回调会写回输出队列，等一小段时间收结果
        result = None
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                result = output_queue.get(timeout=0.1)
                break
            except Exception:
                continue

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["epoch"], 1)
        self.assertEqual(
            [t["translated"] for t in result["translations"]], ["你好", "世界"]
        )


if __name__ == "__main__":
    unittest.main()
