"""翻译子进程管理器.

负责在主进程中维护一个独立的 OCR/翻译子进程，并通过 Qt 信号把结果发回 UI 线程。
"""

import io
import logging
import multiprocessing
import queue
import threading
from typing import Any, Dict, Optional

from PIL import Image
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.worker.translation_worker import run_translation_worker

logger = logging.getLogger(__name__)


class ResultReader(QThread):
    """在独立线程中读取子进程输出队列，并通过信号把结果发到 UI 线程."""

    result_received = pyqtSignal(dict)

    def __init__(self, output_queue: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._output_queue = output_queue
        self._running = False

    def run(self) -> None:
        """循环读取结果队列."""
        self._running = True
        while self._running:
            try:
                result = self._output_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            except (EOFError, OSError):
                logger.warning("结果队列异常，读取线程退出")
                break

            if result is None:
                break

            self.result_received.emit(result)

    def stop(self) -> None:
        """请求读取线程退出."""
        self._running = False


class TranslationProcessManager(QObject):
    """管理翻译子进程的生命周期与任务提交.

    Signals:
        finished(items, elapsed): 翻译成功完成。
        error(message): 翻译过程中发生错误。
        debug_image(images): 用于主窗口预览的 PIL 图像列表。
    """

    finished = pyqtSignal(list, float)
    error = pyqtSignal(str)
    debug_image = pyqtSignal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._input_queue: Optional[multiprocessing.Queue] = None
        self._output_queue: Optional[multiprocessing.Queue] = None
        self._process: Optional[multiprocessing.Process] = None
        self._reader: Optional[ResultReader] = None

        self._lock = threading.Lock()
        self._pending_count = 0
        self._job_counter = 0

    def start(self, config_dict: Dict[str, Any]) -> None:
        """启动翻译子进程和结果读取线程."""
        if self._process is not None and self._process.is_alive():
            logger.warning("翻译子进程已在运行，忽略重复启动")
            return

        self._input_queue = multiprocessing.Queue()
        self._output_queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(
            target=run_translation_worker,
            args=(self._input_queue, self._output_queue, config_dict),
            daemon=True,
        )
        self._process.start()

        self._reader = ResultReader(self._output_queue, self)
        self._reader.result_received.connect(self._on_result_received)
        self._reader.start()

        logger.info(f"翻译子进程已启动 (pid={self._process.pid})")

    def stop(self) -> None:
        """安全停止翻译子进程."""
        if self._process is None:
            return

        # 1. 通知子进程退出
        try:
            if self._input_queue is not None:
                self._input_queue.put(None, timeout=1.0)
        except Exception as e:
            logger.warning(f"发送关闭信号失败: {e}")

        # 2. 等待子进程结束
        if self._process.is_alive():
            self._process.join(timeout=5.0)
        if self._process.is_alive():
            logger.warning("翻译子进程未正常退出，强制终止")
            self._process.terminate()
            self._process.join(timeout=1.0)

        # 3. 停止结果读取线程
        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(2000)
            self._reader = None

        # 关闭队列以释放 multiprocessing 后台线程
        if self._input_queue is not None:
            try:
                self._input_queue.close()
            except Exception:
                pass
        if self._output_queue is not None:
            try:
                self._output_queue.close()
            except Exception:
                pass

        self._process = None
        self._input_queue = None
        self._output_queue = None
        with self._lock:
            self._pending_count = 0

        logger.info("翻译子进程已停止")

    def submit_job(self, job_dict: Dict[str, Any]) -> int:
        """向子进程提交一个翻译任务.

        Args:
            job_dict: 任务数据字典，不需要包含 job_id。

        Returns:
            分配的任务 ID。
        """
        with self._lock:
            self._pending_count += 1
            self._job_counter += 1
            job_id = self._job_counter

        job_dict = dict(job_dict)
        job_dict["job_id"] = job_id

        if self._input_queue is not None:
            try:
                self._input_queue.put(job_dict, timeout=1.0)
            except Exception as e:
                logger.error(f"提交翻译任务失败: {e}")
                with self._lock:
                    self._pending_count = max(0, self._pending_count - 1)
        else:
            logger.error("翻译子进程未启动，无法提交任务")

        return job_id

    def is_busy(self) -> bool:
        """当前是否有未完成的翻译任务."""
        with self._lock:
            return self._pending_count > 0

    def pending_count(self) -> int:
        """未完成任务数量."""
        with self._lock:
            return self._pending_count

    def _on_result_received(self, result: Dict[str, Any]) -> None:
        """处理从子进程返回的结果."""
        with self._lock:
            self._pending_count = max(0, self._pending_count - 1)

        status = result.get("status")
        if status == "error":
            self.error.emit(result.get("error", "未知错误"))
        elif status == "finished":
            self.finished.emit(
                result.get("items", []), result.get("elapsed", 0.0)
            )
            debug_bytes = result.get("debug_image_bytes")
            if debug_bytes:
                try:
                    if isinstance(debug_bytes, list):
                        images = [
                            Image.open(io.BytesIO(b)) for b in debug_bytes
                        ]
                    else:
                        images = [Image.open(io.BytesIO(debug_bytes))]
                    self.debug_image.emit(images)
                except Exception:
                    logger.exception("解码调试图像失败")
        else:
            logger.warning(f"收到未知状态的结果: {status}")
