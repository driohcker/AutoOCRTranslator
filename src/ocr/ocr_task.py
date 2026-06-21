"""OCR 异步任务.

将 OCR 识别与翻译流程放到后台线程执行，避免阻塞主线程和 GUI.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PIL import Image
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from src.translate.lang_filter import should_translate

if TYPE_CHECKING:
    from src.cache.translation_cache import TranslationCache
    from src.ocr.paddle_ocr import PaddleOCREngine
    from src.translate.translator import Translator

logger = logging.getLogger(__name__)


class OCRSignals(QObject):
    """OCR 任务信号.

    由于 QRunnable 本身不是 QObject，需要单独定义信号对象。
    """

    finished = pyqtSignal(list, float)  # translation_items, elapsed_seconds
    error = pyqtSignal(str)
    debug_image = pyqtSignal(object)  # PIL.Image.Image，用于 GUI 实时预览


def run_ocr_pipeline(
    image: Image.Image,
    scale_ratio: float,
    ocr_engine: "PaddleOCREngine",
    translator: "Translator",
    cache: Optional["TranslationCache"],
    source_lang: str,
    target_lang: str,
    offset: tuple = (0, 0),
    filter_source_lang: bool = True,
    strict_source_lang: bool = False,
) -> List[Dict[str, Any]]:
    """同步执行 OCR + 缓存查询/翻译.

    Args:
        image: 待识别图像。
        scale_ratio: 图像相对原始截图的缩放比例，用于将坐标映射回原始尺寸。
        ocr_engine: OCR 引擎。
        translator: 翻译器。
        cache: 翻译缓存，可选。
        source_lang: 源语言。
        target_lang: 目标语言。
        offset: 图像在原始截图中的偏移量 (x, y)，用于 ROI 裁剪场景。
        filter_source_lang: 是否过滤非源语言文本（如 URL、英文 UI）。
        strict_source_lang: 是否启用严格源语言过滤。

    该函数被后台 OCR 任务调用，也可在测试中单线程直接调用。
    """
    ocr_results = ocr_engine.recognize(image)
    if not ocr_results:
        logger.info("OCR 引擎未返回任何文本")
        return []

    logger.info(f"OCR 原始识别到 {len(ocr_results)} 个文本块")

    # 第一步：过滤并查询缓存
    candidates = []
    to_translate: List[str] = []
    skipped = 0
    for item in ocr_results:
        original = item["text"]

        # 过滤非目标语言文本（如 URL、英文按钮等）
        if filter_source_lang and not should_translate(
            original, source_lang, strict=strict_source_lang
        ):
            skipped += 1
            logger.debug(
                f"跳过非源语言文本(strict={strict_source_lang}): {original}"
            )
            continue

        translated: Optional[str] = None
        if cache is not None:
            translated = cache.get(original, source_lang, target_lang)

        candidate = {
            "original": original,
            "box": item["box"],
            "score": item["score"],
            "translated": translated,
        }
        candidates.append(candidate)

        if translated is None:
            to_translate.append(original)

    if skipped:
        logger.info(
            f"语言过滤跳过 {skipped}/{len(ocr_results)} 个文本块 "
            f"(strict_source_lang={strict_source_lang})"
        )

    if not candidates:
        logger.info("所有 OCR 结果均被过滤，未产生可翻译文本")
        return []

    logger.info(f"进入翻译流程 {len(candidates)} 个文本块")

    # 第二步：批量翻译（减少 API 调用次数）
    if to_translate:
        translated_parts = _batch_translate(
            to_translate, translator, source_lang, target_lang
        )
        for candidate, translated in zip(candidates, translated_parts):
            if candidate["translated"] is None:
                candidate["translated"] = translated
                if cache is not None and translated:
                    cache.set(
                        candidate["original"],
                        source_lang,
                        target_lang,
                        translated,
                    )

    # 第三步：构建结果并映射坐标
    translation_items = []
    for candidate in candidates:
        scaled_box = candidate["box"]
        if scale_ratio < 1.0 or offset != (0, 0):
            scaled_box = [
                (
                    int(x / scale_ratio) + offset[0],
                    int(y / scale_ratio) + offset[1],
                )
                for x, y in candidate["box"]
            ]

        translation_items.append(
            {
                "original": candidate["original"],
                "translated": candidate["translated"] or candidate["original"],
                "box": scaled_box,
                "score": candidate["score"],
            }
        )

    return translation_items


def _batch_translate(
    texts: List[str],
    translator: "Translator",
    source_lang: str,
    target_lang: str,
) -> List[str]:
    """批量翻译多个文本.

    使用换行符连接文本一次性调用翻译 API，减少网络往返。
    如果批量翻译结果数量不匹配或失败，则回退到逐条翻译。
    """
    if not texts:
        return []

    if len(texts) == 1:
        try:
            return [translator.translate(texts[0], source_lang, target_lang)]
        except Exception as e:
            logger.warning(f"翻译失败 '{texts[0]}': {e}")
            return [texts[0]]

    # 用换行符连接，先把原文中的换行替换为空格避免干扰
    joined = "\n".join(t.replace("\n", " ") for t in texts)
    try:
        combined = translator.translate(joined, source_lang, target_lang)
        parts = combined.split("\n")
        if len(parts) == len(texts):
            return parts
        logger.warning(
            f"批量翻译结果数量不匹配: {len(parts)} vs {len(texts)}，回退逐条翻译"
        )
    except Exception as e:
        logger.warning(f"批量翻译失败: {e}，回退逐条翻译")

    # 回退逐条翻译
    results = []
    for text in texts:
        try:
            results.append(translator.translate(text, source_lang, target_lang))
        except Exception as e:
            logger.warning(f"翻译失败 '{text}': {e}")
            results.append(text)
    return results


class OCRTask(QRunnable):
    """在后台线程执行 OCR + 缓存查询/翻译的任务."""

    def __init__(
        self,
        image: Image.Image,
        scale_ratio: float,
        ocr_engine: "PaddleOCREngine",
        translator: "Translator",
        cache: Optional["TranslationCache"],
        source_lang: str,
        target_lang: str,
        offset: tuple = (0, 0),
        filter_source_lang: bool = True,
        strict_source_lang: bool = False,
    ) -> None:
        super().__init__()
        self.image = image
        self.scale_ratio = scale_ratio
        self.ocr_engine = ocr_engine
        self.translator = translator
        self.cache = cache
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.offset = offset
        self.filter_source_lang = filter_source_lang
        self.strict_source_lang = strict_source_lang
        self.signals = OCRSignals()

    def run(self) -> None:
        """执行 OCR 与翻译."""
        start_time = time.perf_counter()
        try:
            self.signals.debug_image.emit(self.image)
            items = run_ocr_pipeline(
                self.image,
                self.scale_ratio,
                self.ocr_engine,
                self.translator,
                self.cache,
                self.source_lang,
                self.target_lang,
                self.offset,
                self.filter_source_lang,
                self.strict_source_lang,
            )
            elapsed = time.perf_counter() - start_time
            self.signals.finished.emit(items, elapsed)
        except Exception as e:
            logger.exception("OCR 任务执行失败")
            self.signals.error.emit(str(e))
