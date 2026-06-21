"""多区域 OCR 异步任务.

用于“自定义区域划分”模式：将多个裁剪后的子区域一次性提交到后台线程，
串行执行 OCR + 翻译，最后合并结果返回主线程.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from src.ocr.ocr_task import run_ocr_pipeline

if TYPE_CHECKING:
    from src.cache.translation_cache import TranslationCache
    from src.ocr.paddle_ocr import PaddleOCREngine
    from src.translate.translator import Translator

logger = logging.getLogger(__name__)

# (裁剪后的图片, 在原始截图中的偏移, 缩放比例)
ZoneOCRInput = Tuple[Image.Image, Tuple[int, int], float]


class MultiZoneOCRSignals(QObject):
    """多区域 OCR 任务信号."""

    finished = pyqtSignal(list, float)  # translation_items, elapsed_seconds
    error = pyqtSignal(str)
    debug_image = pyqtSignal(object)  # PIL.Image.Image，用于 GUI 实时预览


class MultiZoneOCRTask(QRunnable):
    """在后台线程执行多个区域 OCR + 翻译的任务."""

    def __init__(
        self,
        zones: List[ZoneOCRInput],
        ocr_engine: "PaddleOCREngine",
        translator: "Translator",
        cache: Optional["TranslationCache"],
        source_lang: str,
        target_lang: str,
        filter_source_lang: bool = True,
        strict_source_lang: bool = False,
    ) -> None:
        """初始化任务.

        Args:
            zones: 每个元素为 (image, offset, scale_ratio)。
            ocr_engine: OCR 引擎。
            translator: 翻译器。
            cache: 翻译缓存，可选。
            source_lang: 源语言。
            target_lang: 目标语言。
            filter_source_lang: 是否过滤非源语言文本。
            strict_source_lang: 是否启用严格源语言过滤。
        """
        super().__init__()
        self.zones = zones
        self.ocr_engine = ocr_engine
        self.translator = translator
        self.cache = cache
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.filter_source_lang = filter_source_lang
        self.strict_source_lang = strict_source_lang
        self.signals = MultiZoneOCRSignals()

    def run(self) -> None:
        """串行处理每个区域并合并结果."""
        start_time = time.perf_counter()
        all_items: List[Dict[str, Any]] = []

        try:
            for idx, (image, offset, scale_ratio) in enumerate(self.zones):
                logger.info(f"处理区域 {idx + 1}/{len(self.zones)}")
                self.signals.debug_image.emit(image)
                items = run_ocr_pipeline(
                    image=image,
                    scale_ratio=scale_ratio,
                    ocr_engine=self.ocr_engine,
                    translator=self.translator,
                    cache=self.cache,
                    source_lang=self.source_lang,
                    target_lang=self.target_lang,
                    offset=offset,
                    filter_source_lang=self.filter_source_lang,
                    strict_source_lang=self.strict_source_lang,
                )
                all_items.extend(items)

            elapsed = time.perf_counter() - start_time
            logger.info(f"多区域 OCR 完成，共 {len(all_items)} 个文本块，耗时 {elapsed:.2f}s")
            self.signals.finished.emit(all_items, elapsed)
        except Exception as e:
            logger.exception("多区域 OCR 任务执行失败")
            self.signals.error.emit(str(e))
