"""多区域 OCR 任务单元测试."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtCore import QEventLoop, QThreadPool, QTimer
from PyQt6.QtWidgets import QApplication

from src.ocr.multi_zone_ocr_task import MultiZoneOCRTask


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestMultiZoneOCRTask(unittest.TestCase):
    """测试 MultiZoneOCRTask."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def _process_events(self, timeout_ms: int = 200) -> None:
        """处理 Qt 事件直到超时."""
        loop = QEventLoop()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    def _make_mock_ocr(self, boxes_per_call):
        """创建按调用次数返回不同结果的 OCR 引擎."""
        ocr_engine = MagicMock()
        call_count = [0]

        def recognize(image):
            idx = call_count[0]
            call_count[0] += 1
            box = boxes_per_call[idx]
            return [
                {
                    "text": f"text{idx}",
                    "box": box,
                    "score": 0.95,
                }
            ]

        ocr_engine.recognize = recognize
        return ocr_engine

    def test_multi_zone_task_merges_offsets(self):
        """测试多区域任务能合并不同 offset 的识别结果."""
        ocr_engine = self._make_mock_ocr(
            [
                [(10, 10), (50, 10), (50, 30), (10, 30)],
                [(5, 5), (40, 5), (40, 25), (5, 25)],
            ]
        )
        translator = MagicMock()
        translator.translate = MagicMock(side_effect=["你好", "世界"])
        cache = MagicMock()
        cache.get = MagicMock(return_value=None)
        cache.set = MagicMock()

        # 两个 100x100 的子图，分别位于原始截图 (0,0) 和 (100,50)
        zones = [
            (Image.new("RGB", (100, 100)), (0, 0), 1.0),
            (Image.new("RGB", (100, 100)), (100, 50), 1.0),
        ]

        task = MultiZoneOCRTask(
            zones=zones,
            ocr_engine=ocr_engine,
            translator=translator,
            cache=cache,
            source_lang="ja",
            target_lang="zh-CN",
        )

        finished_items = []

        def on_finished(items, elapsed):
            finished_items.extend(items)

        task.signals.finished.connect(on_finished)
        QThreadPool.globalInstance().start(task)

        self._process_events(500)

        self.assertEqual(len(finished_items), 2)
        # 第一个区域无偏移
        self.assertEqual(finished_items[0]["box"], [(10, 10), (50, 10), (50, 30), (10, 30)])
        # 第二个区域应加上 offset (100, 50)
        self.assertEqual(
            finished_items[1]["box"],
            [(105, 55), (140, 55), (140, 75), (105, 75)],
        )

    def test_multi_zone_task_empty_zones(self):
        """测试空区域列表直接返回空结果."""
        ocr_engine = MagicMock()
        translator = MagicMock()
        cache = MagicMock()

        task = MultiZoneOCRTask(
            zones=[],
            ocr_engine=ocr_engine,
            translator=translator,
            cache=cache,
            source_lang="ja",
            target_lang="zh-CN",
        )

        finished_called = []

        def on_finished(items, elapsed):
            finished_called.append(items)

        task.signals.finished.connect(on_finished)
        QThreadPool.globalInstance().start(task)

        self._process_events(200)

        ocr_engine.recognize.assert_not_called()
        self.assertEqual(finished_called, [[]])


if __name__ == "__main__":
    unittest.main()
