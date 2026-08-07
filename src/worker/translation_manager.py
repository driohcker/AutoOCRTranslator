"""翻译子进程管理器.

负责在主进程中维护一个独立的翻译子进程，并通过 Qt 信号把结果发回 UI 线程。
OCR 已在主进程的 CaptureThread 中完成，这里只负责「纯文本翻译」任务的收发。
"""

import logging
import multiprocessing
import queue
import threading
from typing import Any, Dict, Optional

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
        try:
            # 放入哨兵值唤醒阻塞在 get() 上的线程，使其立即退出
            self._output_queue.put(None, timeout=0.5)
        except Exception:
            pass


class TranslationProcessManager(QObject):
    """管理翻译子进程的生命周期与任务提交.

    只处理纯文本翻译：OCR 结果（已识别文本 + epoch）经 submit_translation_job
    提交，译文经 translation_finished 信号返回；epoch 用于丢弃过期结果。

    Signals:
        translation_finished(result): 翻译完成，result 为 {"job_id", "epoch",
            "translations": [{"id", "translated"}], "elapsed", "status"}。
        error(message): 子进程错误。
    """

    translation_finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._input_queue: Optional[multiprocessing.Queue] = None
        self._output_queue: Optional[multiprocessing.Queue] = None
        self._process: Optional[multiprocessing.Process] = None
        self._reader: Optional[ResultReader] = None

        self._lock = threading.Lock()
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

        logger.info("翻译子进程已停止")

    def submit_translation_job(
        self,
        epoch: int,
        items: list,
        source_lang: str,
        target_lang: str,
    ) -> int:
        """向子进程提交一个纯文本翻译任务.

        Args:
            epoch: OCR 循环代数，用于丢弃过期结果（慢结果返回时画面已变）。
            items: 待翻译项列表，每项 {"id": int, "text": str}。
            source_lang: 源语言。
            target_lang: 目标语言。

        Returns:
            分配的任务 ID（-1 表示提交失败）。
        """
        with self._lock:
            self._job_counter += 1
            job_id = self._job_counter

        job_dict = {
            "job_id": job_id,
            "epoch": epoch,
            "items": items,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

        if self._input_queue is not None:
            try:
                self._input_queue.put(job_dict, timeout=1.0)
                return job_id
            except Exception as e:
                logger.error(f"提交翻译任务失败: {e}")
                return -1
        else:
            logger.error("翻译子进程未启动，无法提交任务")
            return -1

    def _on_result_received(self, result: Dict[str, Any]) -> None:
        """处理从子进程返回的结果."""
        status = result.get("status")
        if status == "error":
            self.error.emit(result.get("error", "未知错误"))
        elif status == "finished":
            self.translation_finished.emit(result)
        else:
            logger.warning(f"收到未知状态的结果: {status}")
