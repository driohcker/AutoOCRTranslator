"""截图工作线程.

在独立的 QThread 中周期性截图、裁剪/缩放 ROI，并把任务提交给翻译子进程。
UI 主线程只接收信号，不做任何阻塞操作。
"""

import logging
from typing import Any, List, Optional

from PIL import Image
from PyQt6.QtCore import QMutex, QThread, QWaitCondition, pyqtSignal

from src.capture.window_capture import WindowCapture
from src.config import config
from src.utils.image_roi import ROI_OCR_PARAMS, prepare_multi_zones, prepare_single_zone

logger = logging.getLogger(__name__)


class CaptureThread(QThread):
    """截图与预处理线程.

    Signals:
        frame_captured(images): 成功抓取并预处理一帧后发出，images 为 PIL.Image 列表，用于主窗口 OCR 预览。
        frame_skipped(count): 因子进程忙而跳过时发出，count 为累计跳帧数。
        window_invalid(): 目标窗口无效时发出，主线程应停止翻译循环。
    """

    frame_captured = pyqtSignal(object)  # List[PIL.Image]
    frame_skipped = pyqtSignal(int)
    window_invalid = pyqtSignal()

    def __init__(
        self,
        hwnd: int,
        manager: Any,
        interval_ms: int = 1000,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._hwnd = hwnd
        self._manager = manager
        self._interval_ms = interval_ms
        self._running = False
        self._skipped_frames = 0
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

    def _build_job(
        self,
        zones: List[tuple[Image.Image, tuple[int, int], float]],
        preset: str,
    ) -> dict[str, Any]:
        """把预处理后的区域打包成可序列化的任务字典."""
        zones_data = []
        for image, offset, scale_ratio in zones:
            zones_data.append(
                {
                    "bytes": image.tobytes(),
                    "mode": image.mode,
                    "size": image.size,
                    "offset": offset,
                    "scale_ratio": scale_ratio,
                }
            )

        return {
            "mode": "multi_zone" if preset == "custom_zones" else "single",
            "zones": zones_data,
            "preset": preset,
            "source_lang": config.get("translate.source_lang", "ja"),
            "target_lang": config.get("translate.target_lang", "zh-CN"),
            "filter_source_lang": config.get("translate.filter_source_lang", True),
            "strict_source_lang": config.get("translate.strict_source_lang", True),
        }

    def run(self) -> None:
        """线程主循环."""
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
            if not capture.is_valid():
                logger.warning("目标窗口无效，截图线程退出")
                self.window_invalid.emit()
                break

            original_image = capture.capture()
            if original_image is None:
                self._sleep()
                continue

            preset = config.get("ocr.roi_preset", "subtitle")
            try:
                zones = self._build_zones(original_image, preset)
            except Exception:
                logger.exception("ROI 预处理失败")
                self._sleep()
                continue

            if not zones:
                logger.warning("没有有效的识别区域，跳过本帧")
                self._sleep()
                continue

            if self._manager.is_busy():
                self._skipped_frames += 1
                logger.info(
                    f"翻译子进程忙，跳过本帧（已累计跳过 {self._skipped_frames} 帧）"
                )
                self.frame_skipped.emit(self._skipped_frames)
                self._sleep()
                continue

            # 发送所有区域的调试图像到主窗口预览
            self.frame_captured.emit([zone[0].copy() for zone in zones])

            job = self._build_job(zones, preset)
            self._manager.submit_job(job)
            self._skipped_frames = 0

            self._sleep()

        logger.info("截图线程已结束")

    def _sleep(self) -> None:
        """等待下一个截图周期，同时响应停止请求."""
        self._sleep_mutex.lock()
        try:
            self._sleep_condition.wait(self._sleep_mutex, self._interval_ms)
        finally:
            self._sleep_mutex.unlock()

    def stop(self) -> None:
        """停止截图线程."""
        self._running = False
        self._sleep_condition.wakeAll()
        if not self.wait(2000):
            logger.warning("截图线程未在 2 秒内退出")
            self.terminate()
