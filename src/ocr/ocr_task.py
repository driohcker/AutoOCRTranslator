"""OCR 识别流程（主进程执行）.

只包含「本地快步骤」：识别 → 语言过滤 → 缓存查询 → 坐标还原。
翻译已完全异步化到子进程（见 src/worker/），本模块不再接触网络。
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PIL import Image

from src.translate.lang_filter import should_translate

if TYPE_CHECKING:
    from src.cache.translation_cache import TranslationCache
    from src.ocr.paddle_ocr import PaddleOCREngine

logger = logging.getLogger(__name__)


def run_ocr_flow(
    image: Image.Image,
    scale_ratio: float,
    ocr_engine: "PaddleOCREngine",
    cache: Optional["TranslationCache"],
    source_lang: str,
    target_lang: str,
    offset: tuple = (0, 0),
    filter_source_lang: bool = True,
    strict_source_lang: bool = False,
) -> List[Dict[str, Any]]:
    """同步执行 OCR + 缓存查询（不联网）.

    Args:
        image: 待识别图像。
        scale_ratio: 图像相对原始截图的缩放比例，用于将坐标映射回原始尺寸。
        ocr_engine: OCR 引擎。
        cache: 翻译缓存，可选。
        source_lang: 源语言。
        target_lang: 目标语言。
        offset: 图像在原始截图中的偏移量 (x, y)，用于 ROI 裁剪场景。
        filter_source_lang: 是否过滤非源语言文本（如 URL、英文 UI）。
        strict_source_lang: 是否启用严格源语言过滤。

    Returns:
        translation_items 列表，每项 {original, translated, box, score}；
        translated 为缓存命中时的译文，未命中为 None（由调用方决定
        是否提交给翻译子进程异步补齐）。
    """
    start_time = time.perf_counter()
    ocr_results = ocr_engine.recognize(image)
    if not ocr_results:
        logger.debug("OCR 引擎未返回任何文本")
        return []

    logger.debug(f"OCR 原始识别到 {len(ocr_results)} 个文本块")

    candidates: List[Dict[str, Any]] = []
    skipped = 0
    for item in ocr_results:
        original = item["text"]

        # 过滤非目标语言文本（如 URL、英文按钮等）
        if filter_source_lang and not should_translate(
            original, source_lang, strict=strict_source_lang
        ):
            skipped += 1
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

    if skipped:
        logger.debug(
            f"语言过滤跳过 {skipped}/{len(ocr_results)} 个文本块 "
            f"(strict_source_lang={strict_source_lang})"
        )

    if not candidates:
        logger.debug("所有 OCR 结果均被过滤，未产生可翻译文本")
        return []

    # 构建结果并映射坐标（ROI 缩放还原到原始截图坐标）
    translation_items: List[Dict[str, Any]] = []
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
                "translated": candidate["translated"],
                "box": scaled_box,
                "score": candidate["score"],
            }
        )

    elapsed = time.perf_counter() - start_time
    logger.info(
        f"OCR 识别完成：{len(translation_items)} 个文本块，耗时 {elapsed * 1000:.0f}ms"
    )
    return translation_items


# 向后兼容：保留旧函数名（translation_worker 已改用新流程，
# 旧实现按纯识别流程转发，不联网）
def run_ocr_pipeline(
    image: Image.Image,
    scale_ratio: float,
    ocr_engine: "PaddleOCREngine",
    translator: Any = None,
    cache: Optional["TranslationCache"] = None,
    source_lang: str = "ja",
    target_lang: str = "zh-CN",
    offset: tuple = (0, 0),
    filter_source_lang: bool = True,
    strict_source_lang: bool = False,
) -> List[Dict[str, Any]]:
    """兼容旧接口：纯识别 + 缓存查询，不再联网翻译.

    翻译已由翻译子进程异步完成；此函数只做识别与缓存查询，
    未命中的项 translated 为 None。
    """
    return run_ocr_flow(
        image=image,
        scale_ratio=scale_ratio,
        ocr_engine=ocr_engine,
        cache=cache,
        source_lang=source_lang,
        target_lang=target_lang,
        offset=offset,
        filter_source_lang=filter_source_lang,
        strict_source_lang=strict_source_lang,
    )


__all__ = ["run_ocr_flow", "run_ocr_pipeline"]
