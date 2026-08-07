"""截图与识别工作线程.

在独立的 QThread 中周期性截图、裁剪/缩放 ROI，并在主进程内完成本地 OCR
（识别 → 语言过滤 → 缓存查询），随后把未命中的纯文本提交给翻译子进程
异步补齐译文。识别循环永不等待网络翻译——翻译慢/失败只影响译文回填，
不影响识别频率（对应 BetterGI 的「慢步骤完全异步化」模式）。

UI 主线程只接收信号，不做任何阻塞操作。
"""

import logging
import time
from typing import Any, Dict, List, Optional

from PIL import Image
from PyQt6.QtCore import QMutex, QThread, QWaitCondition, pyqtSignal

from src.capture.change_detector import ChangeDetector
from src.capture.window_capture import WindowCapture
from src.config import config
from src.ocr.ocr_task import run_ocr_flow
from src.ocr.ocr_utils import create_ocr_engine
from src.utils.image_roi import ROI_OCR_PARAMS, prepare_multi_zones, prepare_single_zone

logger = logging.getLogger(__name__)


class CaptureThread(QThread):
    """截图、变化检测与本地 OCR 线程.

    Signals:
        frame_captured(images): 成功抓取并预处理一帧后发出，images 为 PIL.Image 列表，用于主窗口 OCR 预览。
        frame_skipped(count): 画面无变化而跳过时发出，count 为累计跳帧数。
        ocr_ready(epoch, items, elapsed): 本帧本地 OCR 完成（不联网），items 中
            缓存命中的项已带译文，未命中的项 translated 为 None。
        window_invalid(): 目标窗口无效时发出，主线程应停止翻译循环。
    """

    frame_captured = pyqtSignal(object)  # List[PIL.Image]
    frame_skipped = pyqtSignal(int)
    ocr_ready = pyqtSignal(int, list, float)  # epoch, items, elapsed
    window_invalid = pyqtSignal()

    def __init__(
        self,
        hwnd: int,
        manager: Any,
        interval_ms: int = 1000,
        cache: Optional[Any] = None,
        change_detection: bool = True,
        change_threshold: int = 4,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._hwnd = hwnd
        self._manager = manager
        self._interval_ms = interval_ms
        self._cache = cache
        self._change_detection = change_detection
        self._change_detector = ChangeDetector(threshold=change_threshold)
        self._running = False
        self._skipped_frames = 0
        self._epoch = 0
        self._ocr_engine: Optional[Any] = None
        self._current_preset: Optional[str] = None
        self._sleep_mutex = QMutex()
        self._sleep_condition = QWaitCondition()

    def set_interval(self, interval_ms: int) -> None:
        """动态更新截图间隔."""
        self._interval_ms = interval_ms

    def _read_max_width(self, preset: str) -> int:
        """根据 preset 读取最大 OCR 宽度."""
        if preset in ROI_OCR_PARAMS:
            return ROI_OCR_PARAMS[preset]["max_width"]
        return config.get("ocr.max_width", 480)

    def _build_zones(
        self, original_image: Image.Image, preset: str
    ) -> List[tuple[Image.Image, tuple[int, int], float]]:
        """根据配置把原始截图拆分为一个或多个待识别区域."""
        if preset == "custom_zones":
            roi_zones = config.get("ocr.roi_zones", []) or []
            if not roi_zones:
                logger.warning("自定义区域划分为空，本次按全屏处理")
                roi_zones = [[0.0, 0.0, 1.0, 1.0]]
            return prepare_multi_zones(
                original_image, roi_zones, self._read_max_width(preset)
            )

        custom_roi = config.get("ocr.roi_custom", [0.1, 0.75, 0.8, 0.2])
        max_width = self._read_max_width(preset)
        return [prepare_single_zone(original_image, preset, custom_roi, max_width)]

    def _ensure_ocr(self, preset: str) -> Any:
        """当预设变化时重新初始化 OCR 引擎（本地识别，主进程内）."""
        if self._ocr_engine is not None and self._current_preset == preset:
            return self._ocr_engine

        params = ROI_OCR_PARAMS.get(preset, ROI_OCR_PARAMS["subtitle"])
        engine = config.get("ocr.engine", "rapid")
        lang = config.get("ocr.lang", "japan")
        use_gpu = config.get("ocr.use_gpu", False)
        logger.info(f"初始化 OCR 引擎: engine={engine}, lang={lang}, preset={preset}, use_gpu={use_gpu}")
        self._ocr_engine = create_ocr_engine(engine, lang, params, use_gpu)
        self._current_preset = preset
        # 引擎重建后画面基准可能变化，重置变化检测
        self._change_detector.reset()
        return self._ocr_engine

    def run(self) -> None:
        """线程主循环：采集 → 变化检测 → 本地 OCR → 提交翻译任务."""
        capture = WindowCapture()
        try:
            capture.set_target(self._hwnd)
        except Exception as e:
            logger.warning(f"截图线程设置目标窗口失败: {e}")
            self.window_invalid.emit()
            return

        self._running = True
        logger.info(f"截图线程启动，间隔 {self._interval_ms}ms")

        while self._running:
            # 用 deadline 保证：识别慢于间隔时不再睡眠，直接追上最新帧
            deadline = time.monotonic() + self._interval_ms / 1000.0

            if not capture.is_valid():
                logger.warning("目标窗口无效，截图线程退出")
                self.window_invalid.emit()
                break

            original_image = capture.capture()
            if original_image is None:
                self._sleep_to(deadline)
                continue

            preset = config.get("ocr.roi_preset", "subtitle")
            try:
                zones = self._build_zones(original_image, preset)
            except Exception:
                logger.exception("ROI 预处理失败")
                self._sleep_to(deadline)
                continue

            if not zones:
                logger.warning("没有有效的识别区域，跳过本帧")
                self._sleep_to(deadline)
                continue

            # 便宜优先：画面无变化则跳过本帧，不进入 OCR
            if self._change_detection and not self._change_detector.check(
                [zone[0] for zone in zones]
            ):
                self._skipped_frames += 1
                self.frame_skipped.emit(self._skipped_frames)
                self._sleep_to(deadline)
                continue
            self._skipped_frames = 0

            # 发送所有区域的调试图像到主窗口预览
            self.frame_captured.emit([zone[0].copy() for zone in zones])

            # 主进程内本地 OCR（识别 + 语言过滤 + 缓存查询，不联网）
            try:
                ocr_engine = self._ensure_ocr(preset)
            except Exception:
                logger.exception("OCR 引擎初始化失败")
                self._sleep_to(deadline)
                continue

            source_lang = config.get("translate.source_lang", "ja")
            target_lang = config.get("translate.target_lang", "zh-CN")
            filter_source_lang = config.get("translate.filter_source_lang", True)
            strict_source_lang = config.get("translate.strict_source_lang", True)

            start_time = time.perf_counter()
            try:
                all_items: List[Dict[str, Any]] = []
                for image, offset, scale_ratio in zones:
                    items = run_ocr_flow(
                        image=image,
                        scale_ratio=scale_ratio,
                        ocr_engine=ocr_engine,
                        cache=self._cache,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        offset=offset,
                        filter_source_lang=filter_source_lang,
                        strict_source_lang=strict_source_lang,
                    )
                    all_items.extend(items)
            except Exception:
                logger.exception("本地 OCR 失败")
                self._sleep_to(deadline)
                continue
            elapsed = time.perf_counter() - start_time

            self._epoch += 1
            epoch = self._epoch
            self.ocr_ready.emit(epoch, all_items, elapsed)

            # 未命中缓存的文本异步提交翻译（只传纯文本，不带图像）
            pending_lines = [
                {"id": idx, "text": item["original"]}
                for idx, item in enumerate(all_items)
                if item.get("translated") is None
            ]
            if pending_lines:
                self._manager.submit_translation_job(
                    epoch, pending_lines, source_lang, target_lang
                )

            self._sleep_to(deadline)

        logger.info("截图线程已结束")

    def _sleep_to(self, deadline: float) -> None:
        """睡眠到 deadline，同时响应停止请求；已过期则立即返回（追帧）."""
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            return
        self._sleep_mutex.lock()
        try:
            self._sleep_condition.wait(self._sleep_mutex, remaining_ms)
        finally:
            self._sleep_mutex.unlock()

    def stop(self) -> None:
        """停止截图线程."""
        self._running = False
        self._sleep_condition.wakeAll()
        if not self.wait(2000):
            logger.warning("截图线程未在 2 秒内退出")
            self.terminate()
