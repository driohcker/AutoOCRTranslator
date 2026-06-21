"""翻译子进程工作逻辑.

本模块运行在独立的 Python 子进程中，负责：
- 初始化 OCR 引擎、翻译器、缓存。
- 从输入队列接收截图任务。
- 执行 OCR + 翻译 + 缓存读写。
- 把结果写回输出队列。

注意：为了不把 PyQt 事件循环带入子进程，本模块不导入任何 GUI 相关代码。
"""

import io
import logging
import time
from typing import Any, Dict, List, Optional

from PIL import Image

from src.cache.translation_cache import TranslationCache
from src.ocr.ocr_task import run_ocr_pipeline
from src.ocr.ocr_utils import create_ocr_engine
from src.translate.translator import create_translator
from src.utils.image_roi import ROI_OCR_PARAMS

logger = logging.getLogger(__name__)


def _decode_image(image_dict: Dict[str, Any]) -> Image.Image:
    """把任务中的图像字节还原为 PIL.Image."""
    return Image.frombytes(
        image_dict["mode"],
        tuple(image_dict["size"]),
        image_dict["bytes"],
    )


def _encode_image(image: Image.Image) -> bytes:
    """把 PIL.Image 编码为 PNG 字节，用于 GUI 预览."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _init_modules(
    config_dict: Dict[str, Any]
) -> tuple[Any, Any, Optional[TranslationCache]]:
    """根据配置初始化 OCR、翻译器、缓存.

    Returns:
        (ocr_engine, translator, cache_or_None)。
    """
    ocr_config = config_dict.get("ocr", {})
    translate_config = config_dict.get("translate", {})
    cache_config = config_dict.get("cache", {})

    engine = ocr_config.get("engine", "rapid")
    lang = ocr_config.get("lang", "japan")
    use_gpu = ocr_config.get("use_gpu", False)
    # 默认使用 subtitle 预设参数初始化，实际按任务中的 preset 再调整
    preset = ocr_config.get("preset", "subtitle")
    params = ROI_OCR_PARAMS.get(preset, ROI_OCR_PARAMS["subtitle"])

    ocr = create_ocr_engine(engine, lang, params, use_gpu)
    translator = create_translator(translate_config)

    cache: Optional[TranslationCache] = None
    if cache_config.get("enabled", True):
        db_path = cache_config.get("db_path", "data/cache/translations.db")
        ttl_days = cache_config.get("ttl_days", 30)
        cache = TranslationCache(db_path=db_path)
        try:
            cleaned = cache.cleanup_expired(ttl_days)
            if int(cleaned) > 0:
                logger.info(f"子进程启动时清理了 {cleaned} 条过期缓存")
        except (TypeError, ValueError):
            pass

    return ocr, translator, cache


def _ensure_ocr_for_preset(
    ocr: Any,
    current_preset: str,
    new_preset: str,
    config_dict: Dict[str, Any],
) -> Any:
    """当任务预设变化时重新初始化 OCR 引擎."""
    if current_preset == new_preset:
        return ocr

    params = ROI_OCR_PARAMS.get(new_preset, ROI_OCR_PARAMS["subtitle"])
    engine = config_dict.get("ocr", {}).get("engine", "rapid")
    lang = config_dict.get("ocr", {}).get("lang", "japan")
    use_gpu = config_dict.get("ocr", {}).get("use_gpu", False)
    logger.info(f"子进程切换 OCR 预设: {current_preset} -> {new_preset}")
    return create_ocr_engine(engine, lang, params, use_gpu)


def _process_job(
    job: Dict[str, Any],
    ocr: Any,
    translator: Any,
    cache: Optional[TranslationCache],
    current_preset: str,
    config_dict: Dict[str, Any],
) -> tuple[Any, str]:
    """处理一个翻译任务.

    Returns:
        (新 ocr 引擎实例, 当前预设名称)。如果 OCR 引擎被重新初始化，则返回新实例。
    """
    start_time = time.perf_counter()
    preset = job.get("preset", "subtitle")
    ocr = _ensure_ocr_for_preset(ocr, current_preset, preset, config_dict)

    source_lang = job.get("source_lang", "ja")
    target_lang = job.get("target_lang", "zh-CN")
    filter_source_lang = job.get("filter_source_lang", True)
    strict_source_lang = job.get("strict_source_lang", True)

    try:
        all_items: List[Dict[str, Any]] = []
        debug_images: List[Image.Image] = []

        zones = job.get("zones", [])
        for idx, zone_dict in enumerate(zones):
            image = _decode_image(zone_dict)
            debug_images.append(image)

            logger.info(
                f"子进程处理区域 {idx + 1}/{len(zones)}, 尺寸 {image.size}, "
                f"预设={preset}"
            )
            items = run_ocr_pipeline(
                image=image,
                scale_ratio=zone_dict.get("scale_ratio", 1.0),
                ocr_engine=ocr,
                translator=translator,
                cache=cache,
                source_lang=source_lang,
                target_lang=target_lang,
                offset=tuple(zone_dict.get("offset", (0, 0))),
                filter_source_lang=filter_source_lang,
                strict_source_lang=strict_source_lang,
            )
            all_items.extend(items)

        elapsed = time.perf_counter() - start_time
        result: Dict[str, Any] = {
            "status": "finished",
            "items": all_items,
            "elapsed": elapsed,
            "error": None,
        }
        if debug_images:
            try:
                result["debug_image_bytes"] = [
                    _encode_image(img) for img in debug_images
                ]
            except Exception:
                logger.exception("编码调试图像失败")

        return ocr, preset, result
    except Exception as e:
        logger.exception("子进程处理任务失败")
        return ocr, preset, {"status": "error", "error": str(e)}


def run_translation_worker(
    input_queue: Any, output_queue: Any, config_dict: Dict[str, Any]
) -> None:
    """翻译子进程入口函数.

    Args:
        input_queue: 接收任务的 multiprocessing.Queue。
        output_queue: 发送结果的 multiprocessing.Queue。
        config_dict: 应用配置快照。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("翻译子进程启动")

    try:
        ocr, translator, cache = _init_modules(config_dict)
    except Exception as e:
        logger.exception("翻译子进程初始化失败")
        output_queue.put({"status": "error", "error": f"初始化失败: {e}"})
        return

    current_preset = config_dict.get("ocr", {}).get("preset", "subtitle")

    while True:
        try:
            job = input_queue.get()
        except (EOFError, OSError):
            logger.info("输入队列已关闭，子进程退出")
            break

        if job is None or job.get("shutdown"):
            logger.info("收到关闭信号，翻译子进程退出")
            break

        try:
            ocr, current_preset, result = _process_job(
                job, ocr, translator, cache, current_preset, config_dict
            )
        except Exception as e:
            logger.exception("翻译子进程处理任务失败")
            result = {"status": "error", "error": str(e)}

        try:
            output_queue.put(result)
        except Exception:
            logger.exception("向输出队列写入结果失败")

    logger.info("翻译子进程已结束")
