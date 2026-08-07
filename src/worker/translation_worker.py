"""翻译子进程工作逻辑.

本模块运行在独立的 Python 子进程中，职责被简化为「纯翻译」：
- 初始化翻译器、缓存。
- 从输入队列接收「待翻译文本」任务（OCR 已移到主进程完成，只传文本）。
- 用线程池并发翻译（默认 2 线程），翻译网络延迟不再阻塞任何识别逻辑。
- 把译文写回输出队列。

注意：为了不把 PyQt 事件循环带入子进程，本模块不导入任何 GUI 相关代码。
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from src.cache.translation_cache import TranslationCache
from src.translate.base import TranslationError
from src.translate.translator import Translator, create_translator

logger = logging.getLogger(__name__)


def _batch_translate(
    texts: List[str],
    translator: Translator,
    source_lang: str,
    target_lang: str,
) -> List[str]:
    """批量翻译文本列表.

    多条文本通过换行合并为一次 API 调用；若返回条数不匹配或失败，
    回退逐条翻译；单条失败时以原文兜底（显示原文而非空白）。
    """
    if not texts:
        return []

    if len(texts) == 1:
        try:
            return [translator.translate(texts[0], source_lang, target_lang)]
        except Exception as e:
            logger.warning(f"翻译失败 '{texts[0]}': {e}")
            return [texts[0]]

    # 多条文本合并为一次请求（换行分隔），减少 API 调用次数
    joined = "\n".join(t.replace("\n", " ") for t in texts)
    try:
        result = translator.translate(joined, source_lang, target_lang)
        parts = result.split("\n")
        if len(parts) == len(texts):
            return parts
        logger.warning(
            f"批量翻译条数不匹配（期望 {len(texts)}，实际 {len(parts)}），逐条回退"
        )
    except Exception as e:
        logger.warning(f"批量翻译失败，逐条回退: {e}")

    # 回退：逐条翻译，失败以原文兜底
    results: List[str] = []
    for text in texts:
        try:
            results.append(translator.translate(text, source_lang, target_lang))
        except Exception as e:
            logger.warning(f"单条翻译失败，以原文兜底: {e}")
            results.append(text)
    return results


def _init_translator(config_dict: Dict[str, Any]) -> Translator:
    """根据配置初始化翻译器."""
    translate_config = config_dict.get("translate", {})
    return create_translator(translate_config)


def _init_cache(config_dict: Dict[str, Any]) -> Optional[TranslationCache]:
    """根据配置初始化缓存."""
    cache_config = config_dict.get("cache", {})
    if not cache_config.get("enabled", True):
        return None

    db_path = cache_config.get("db_path", "data/cache/translations.db")
    ttl_days = cache_config.get("ttl_days", 30)
    cache = TranslationCache(db_path=db_path)
    try:
        cleaned = cache.cleanup_expired(ttl_days)
        if int(cleaned) > 0:
            logger.info(f"子进程启动时清理了 {cleaned} 条过期缓存")
    except (TypeError, ValueError):
        pass
    return cache


def _process_job(
    job: Dict[str, Any],
    translator: Translator,
    cache: Optional[TranslationCache],
) -> Dict[str, Any]:
    """处理一个翻译任务：查缓存 → 批量翻译 → 写回缓存.

    Args:
        job: 形如 {
            "job_id": int, "epoch": int,
            "items": [{"id": int, "text": str}, ...],
            "source_lang": str, "target_lang": str,
        }。

    Returns:
        结果字典，translations 与 items 按 id 一一对应；
        每项含 {"id", "original", "translated"}，original 供主进程按文本合并译文。
    """
    start_time = time.perf_counter()
    job_id = job.get("job_id", -1)
    epoch = job.get("epoch", -1)
    source_lang = job.get("source_lang", "ja")
    target_lang = job.get("target_lang", "zh-CN")

    items: List[Dict[str, Any]] = job.get("items", [])
    translations: List[Dict[str, Any]] = []

    # 第一步：缓存命中直接出译文
    to_translate: List[Dict[str, Any]] = []
    for item in items:
        text = item.get("text", "")
        translated: Optional[str] = None
        if cache is not None and text:
            translated = cache.get(text, source_lang, target_lang)
        if translated is not None:
            translations.append(
                {
                    "id": item.get("id"),
                    "original": text,
                    "translated": translated,
                }
            )
        else:
            to_translate.append(item)

    # 第二步：未命中的文本批量翻译（网络调用，线程池中执行）
    if to_translate:
        texts = [item.get("text", "") for item in to_translate]
        parts = _batch_translate(texts, translator, source_lang, target_lang)
        for item, translated in zip(to_translate, parts):
            if cache is not None and translated:
                cache.set(item.get("text", ""), source_lang, target_lang, translated)
            translations.append(
                {
                    "id": item.get("id"),
                    "original": item.get("text", ""),
                    "translated": translated or "",
                }
            )

    elapsed = time.perf_counter() - start_time
    logger.info(
        f"翻译任务完成: job_id={job_id}, epoch={epoch}, "
        f"items={len(items)}, 耗时 {elapsed * 1000:.0f}ms"
    )
    return {
        "status": "finished",
        "job_id": job_id,
        "epoch": epoch,
        "translations": translations,
        "elapsed": elapsed,
        "error": None,
    }


def run_translation_worker(
    input_queue: Any, output_queue: Any, config_dict: Dict[str, Any]
) -> None:
    """翻译子进程入口函数.

    调度线程从输入队列取任务，提交到 ThreadPoolExecutor 并发执行；
    执行结果由回调写回输出队列。网络翻译与识别完全解耦。

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
        translator = _init_translator(config_dict)
        cache = _init_cache(config_dict)
    except Exception as e:
        logger.exception("翻译子进程初始化失败")
        output_queue.put({"status": "error", "error": f"初始化失败: {e}"})
        return

    concurrency = int(config_dict.get("translate", {}).get("concurrency", 2))
    concurrency = max(1, min(concurrency, 8))
    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="trans")

    def _handle_done(future) -> None:
        try:
            result = future.result()
        except Exception as e:
            logger.exception("翻译任务执行失败")
            result = {"status": "error", "error": str(e)}
        try:
            output_queue.put(result)
        except Exception:
            logger.exception("向输出队列写入结果失败")

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
            future = executor.submit(_process_job, job, translator, cache)
            future.add_done_callback(_handle_done)
        except Exception as e:
            logger.exception("提交翻译任务失败")
            output_queue.put(
                {
                    "status": "error",
                    "job_id": job.get("job_id", -1),
                    "epoch": job.get("epoch", -1),
                    "error": str(e),
                }
            )

    # 停止接收新任务；进行中的任务交由回调收尾（父进程 stop() 有超时兜底）
    executor.shutdown(wait=False, cancel_futures=True)
    logger.info("翻译子进程已结束")
