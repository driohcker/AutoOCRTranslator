"""应用主控制模块.

整合窗口捕获、OCR、翻译、缓存、覆盖层模块，实现完整的翻译工作流。

为了避免 UI 卡顿，本模块不再直接执行截图与 OCR/翻译：
- 截图与 ROI 预处理运行在独立的 QThread（CaptureThread）。
- OCR、翻译、缓存运行在独立的子进程（TranslationProcessManager）。
- UI 主线程只负责事件处理、overlay 绘制和状态更新。
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QStyle,
)

from src.cache.translation_cache import TranslationCache
from src.capture.capture_thread import CaptureThread
from src.capture.window_capture import WindowCapture, select_window_dialog
from src.config import config
from src.overlay.overlay_window import OverlayWindow
from src.worker.translation_manager import TranslationProcessManager

logger = logging.getLogger(__name__)


class App:
    """应用主控制类."""

    def __init__(self) -> None:
        """初始化应用."""
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.capture = WindowCapture()
        self.cache: Optional[TranslationCache] = None
        self.overlay = OverlayWindow()

        self.translation_manager = TranslationProcessManager()
        self.capture_thread: Optional[CaptureThread] = None

        self.is_running = False

        # 本地 OCR 状态：epoch 用于丢弃过期的异步译文
        self._current_epoch = 0
        self._current_items: List[Dict[str, Any]] = []

        # 悬浮日志窗口
        self.log_overlay: Optional[Any] = None
        self._log_overlay_handler: Optional[Any] = None

        # 主控制窗口
        self.main_window: Optional[Any] = None
        self._target_title = ""
        self._skipped_frames = 0

        # 用于检测 OCR 相关配置变化后是否需要重启子进程
        self._last_ocr_config: Dict[str, Any] = {}

        # 系统托盘菜单（托盘图标在 run() 中创建）
        self.tray_menu = QMenu()
        self.action_show = QAction("显示主窗口")
        self.action_show.triggered.connect(self.show_main_window)
        self.action_toggle = QAction("开始翻译")
        self.action_toggle.triggered.connect(self._toggle_translation)
        self.action_quit = QAction("退出")
        self.action_quit.triggered.connect(self.quit)
        self.tray_menu.addAction(self.action_show)
        self.tray_menu.addAction(self.action_toggle)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.action_quit)

        self.tray_icon: Optional[QSystemTrayIcon] = None

    def init(self) -> None:
        """初始化日志和各功能模块."""
        self._setup_logging()

        # 缓存模块（仅用于主界面统计与清空，实际翻译缓存在子进程中）
        cache_enabled = config.get("cache.enabled", True)
        if cache_enabled:
            db_path = config.get("cache.db_path", "data/cache/translations.db")
            ttl_days = config.get("cache.ttl_days", 30)
            logger.info(f"初始化缓存: db_path={db_path}, ttl_days={ttl_days}")
            self.cache = TranslationCache(db_path=db_path)
            cleaned = self.cache.cleanup_expired(ttl_days)
            try:
                if int(cleaned) > 0:
                    logger.info(f"启动时清理了 {cleaned} 条过期缓存")
            except (TypeError, ValueError):
                pass

        # 覆盖层样式
        self.overlay.apply_style(
            font_family=config.get("overlay.font_family", "Microsoft YaHei"),
            font_size=config.get("overlay.font_size", 18),
            font_color=config.get("overlay.font_color", "#FFFFFF"),
            bg_color=config.get("overlay.bg_color", "#80000000"),
            border_color=config.get("overlay.border_color", "#FF000000"),
            max_width=config.get("overlay.max_width", 400),
        )
        self.overlay.set_zones(config.get("ocr.roi_zones", []) or [])

        # 创建主控制窗口
        from src.gui.main_window import MainWindow

        self.main_window = MainWindow(self)
        self.main_window.show()
        logger.info("主控制窗口已显示")

        # 初始化悬浮日志窗口（如果启用）
        if config.get("log_overlay.enabled", False):
            self.show_log_overlay()

    def _setup_logging(self) -> None:
        """配置日志输出到控制台和文件."""
        log_dir = Path("data/cache")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding="utf-8"),
            ],
        )

    def select_window(self) -> bool:
        """弹出窗口选择对话框，让用户选择目标窗口.

        Returns:
            是否成功选择了有效窗口.
        """
        windows = self.capture.list_windows()
        if not windows:
            QMessageBox.warning(None, "提示", "未找到可见窗口，请打开游戏窗口后重试。")
            return False

        hwnd = select_window_dialog(windows)
        if hwnd is None:
            return False

        title = ""
        for info_hwnd, info_title in windows:
            if info_hwnd == hwnd:
                title = info_title
                break

        self.capture.set_target(hwnd)
        self.overlay.set_target_window(hwnd)
        self._target_title = title
        if self.main_window is not None:
            self.main_window.update_status(self.is_running, self._target_title)
        logger.info(f"已选择目标窗口: hwnd={hwnd}, title={title}")
        return True

    def start(self) -> None:
        """启动翻译循环."""
        if not self.capture.is_valid():
            if not self.select_window():
                logger.info("用户取消选择窗口，未启动翻译")
                return

        hwnd = self.capture.get_target()
        if hwnd is None:
            logger.error("目标窗口句柄为空，无法启动")
            return

        interval = config.get("capture.interval_ms", 1000)

        # 启动翻译子进程
        config_dict: Dict[str, Any] = config.raw
        self.translation_manager.start(config_dict)
        self._last_ocr_config = {
            "engine": config_dict.get("ocr", {}).get("engine", "rapid"),
            "use_gpu": config_dict.get("ocr", {}).get("use_gpu", False),
        }

        # 启动截图线程（主进程内完成本地 OCR + 变化检测）
        self.capture_thread = CaptureThread(
            hwnd=hwnd,
            manager=self.translation_manager,
            interval_ms=interval,
            cache=self.cache,
            change_detection=config.get("capture.change_detection", True),
            change_threshold=config.get("capture.change_threshold", 4),
        )
        self.capture_thread.frame_captured.connect(self._on_ocr_debug_image)
        self.capture_thread.frame_skipped.connect(self._on_frame_skipped)
        self.capture_thread.ocr_ready.connect(self._on_ocr_ready)
        self.capture_thread.window_invalid.connect(self._on_capture_window_invalid)
        self.capture_thread.finished.connect(self._on_capture_thread_finished)
        self.capture_thread.start()

        # 连接翻译子进程结果信号（译文异步回填）
        self.translation_manager.translation_finished.connect(
            self._on_translation_finished
        )
        self.translation_manager.error.connect(self._on_ocr_error)

        self.is_running = True
        self.overlay.show()
        if self.action_toggle is not None:
            self.action_toggle.setText("停止翻译")
        if self.main_window is not None:
            self.main_window.update_status(True, self._target_title)
        logger.info(f"翻译循环已启动，截图间隔 {interval}ms")

    def stop(self) -> None:
        """停止翻译循环."""
        if not self.is_running and self.capture_thread is None:
            return

        self.is_running = False
        self.overlay.hide()

        # 先停止截图线程，再停止翻译子进程
        if self.capture_thread is not None:
            self.capture_thread.stop()
            self.capture_thread = None

        self.translation_manager.stop()

        if self.action_toggle is not None:
            self.action_toggle.setText("开始翻译")
        if self.main_window is not None:
            self.main_window.update_status(False, self._target_title)
        logger.info("翻译循环已停止")

    def show_log_overlay(self) -> None:
        """显示悬浮日志窗口."""
        if self.log_overlay is not None:
            self.log_overlay.show()
            self.log_overlay.raise_()
            self.log_overlay.activateWindow()
            self._sync_log_overlay_button(True)
            return

        from src.gui.log_overlay_window import LogOverlayHandler, LogOverlayWindow

        self.log_overlay = LogOverlayWindow()
        self.log_overlay.destroyed.connect(self._on_log_overlay_destroyed)
        self.log_overlay.show()

        self._log_overlay_handler = LogOverlayHandler(self.log_overlay)
        self._log_overlay_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(self._log_overlay_handler)
        self._sync_log_overlay_button(True)
        logger.info("悬浮日志窗口已显示")

    def hide_log_overlay(self) -> None:
        """隐藏悬浮日志窗口."""
        if self.log_overlay is not None:
            self.log_overlay.close()
            self.log_overlay = None
        if self._log_overlay_handler is not None:
            logging.getLogger().removeHandler(self._log_overlay_handler)
            self._log_overlay_handler = None
        self._sync_log_overlay_button(False)

    def toggle_log_overlay(self) -> None:
        """切换悬浮日志窗口显示状态."""
        if self.log_overlay is None:
            self.show_log_overlay()
        else:
            self.hide_log_overlay()

    def _sync_log_overlay_button(self, visible: bool) -> None:
        """同步主窗口悬浮日志按钮状态."""
        if self.main_window is not None:
            self.main_window.btn_log_overlay.setChecked(visible)

    def _on_log_overlay_destroyed(self) -> None:
        """悬浮日志窗口被外部关闭时的清理."""
        self.log_overlay = None
        if self._log_overlay_handler is not None:
            logging.getLogger().removeHandler(self._log_overlay_handler)
            self._log_overlay_handler = None
        self._sync_log_overlay_button(False)

    def quit(self) -> None:
        """完全退出应用."""
        logger.info("正在退出应用...")
        self.stop()
        self.hide_log_overlay()
        self.translation_manager.stop()
        if self.tray_icon is not None:
            self.tray_icon.hide()
        self.app.quit()

    def _on_frame_skipped(self, count: int) -> None:
        """截图线程报告本帧被跳过."""
        self._skipped_frames = count

    def _on_capture_window_invalid(self) -> None:
        """截图线程报告目标窗口无效."""
        logger.warning("目标窗口无效，停止翻译循环")
        self.stop()

    def _on_capture_thread_finished(self) -> None:
        """截图线程正常结束后的清理."""
        logger.info("截图线程已结束")
        self.capture_thread = None

    def _on_ocr_ready(
        self, epoch: int, items: List[Dict[str, Any]], elapsed: float
    ) -> None:
        """本地 OCR 完成回调（主线程）：立即显示原文与缓存译文.

        未命中的译文由 _on_translation_finished 异步回填；本回调不等待网络。
        """
        if not self.is_running:
            return

        self._current_epoch = epoch
        self._current_items = items
        logger.info(
            f"OCR 识别完成，识别到 {len(items)} 个文本块，耗时 {elapsed * 1000:.0f}ms"
        )

        if items:
            self.overlay.update_translations(items)
            if self.main_window is not None:
                self.main_window.update_recent(items)
        else:
            logger.debug("本帧未识别到文本，保留上一帧覆盖层")

        if self.main_window is not None:
            self.main_window.update_stats()
            self.main_window.update_performance(elapsed, self._skipped_frames)
        self._skipped_frames = 0

    def _on_translation_finished(self, result: Dict[str, Any]) -> None:
        """翻译子进程译文回调（主线程）：把异步译文合并进当前显示.

        慢结果返回时若画面已更新（epoch 过期）则丢弃，避免旧译文错位。
        """
        if not self.is_running:
            return

        epoch = result.get("epoch", -1)
        translations = result.get("translations", [])

        if epoch < self._current_epoch:
            logger.debug(f"丢弃过期译文（epoch {epoch} < 当前 {self._current_epoch}）")
            return

        if not translations or not self._current_items:
            return

        # 按 original 文本合并译文（同一文本按出现顺序匹配）
        by_text: Dict[str, list] = {}
        for t in translations:
            text = t.get("translated", "")
            if text:
                by_text.setdefault(t.get("original", ""), []).append(text)

        merged = []
        consumed: Dict[str, int] = {}
        for item in self._current_items:
            new_item = dict(item)
            original = item.get("original", "")
            pool = by_text.get(original, [])
            if pool:
                idx = consumed.get(original, 0)
                if idx < len(pool):
                    new_item["translated"] = pool[idx]
                    consumed[original] = idx + 1
            merged.append(new_item)

        self.overlay.update_translations(merged)

    def _on_ocr_debug_image(self, images: Any) -> None:
        """OCR 调试图像回调（主线程）：把当前识别批次对应的截图显示到主窗口."""
        if self.main_window is not None:
            self.main_window.set_ocr_preview(images)

    def _on_ocr_error(self, error_message: str) -> None:
        """翻译子进程错误回调（主线程）."""
        logger.error(f"翻译子进程错误: {error_message}")

    def show_main_window(self) -> None:
        """显示/前置主控制窗口."""
        if self.main_window is None:
            return
        if self.main_window.isMinimized():
            self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.main_window.show()

    def show_settings(self) -> None:
        """打开设置窗口并应用更改."""
        from src.gui.settings_window import SettingsWindow

        dialog = SettingsWindow()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config.load()
            self._apply_config()
            logger.info("配置已更新")

    def _apply_config(self) -> None:
        """将最新配置应用到当前运行实例."""
        try:
            self.overlay.apply_style(
                font_family=config.get("overlay.font_family", "Microsoft YaHei"),
                font_size=config.get("overlay.font_size", 18),
                font_color=config.get("overlay.font_color", "#FFFFFF"),
                bg_color=config.get("overlay.bg_color", "#80000000"),
                border_color=config.get("overlay.border_color", "#FF000000"),
                max_width=config.get("overlay.max_width", 400),
            )

            # 更新截图间隔
            if self.is_running and self.capture_thread is not None:
                interval = config.get("capture.interval_ms", 1000)
                self.capture_thread.set_interval(interval)
                logger.info(f"截图间隔已更新为 {interval}ms")

            self.overlay.set_zones(config.get("ocr.roi_zones", []) or [])

            # 如果 OCR 引擎或 GPU 设置变化且正在运行，自动重启子进程
            new_ocr_config = {
                "engine": config.get("ocr.engine", "rapid"),
                "use_gpu": config.get("ocr.use_gpu", False),
            }
            if self._last_ocr_config and new_ocr_config != self._last_ocr_config:
                self._last_ocr_config = new_ocr_config
                if self.is_running:
                    logger.info(
                        "OCR 引擎或 GPU 设置发生变化，正在重启翻译循环..."
                    )
                    self.stop()
                    self.start()
        except Exception as e:
            logger.exception("应用配置失败")
            QMessageBox.warning(None, "配置应用失败", f"应用配置时出错:\n{e}")

    def _toggle_translation(self) -> None:
        """切换翻译循环启停状态."""
        if self.is_running:
            self.stop()
        else:
            self.start()

    def _setup_tray_icon(self) -> bool:
        """创建并显示系统托盘图标.

        Returns:
            是否成功显示托盘图标.
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用")
            return False

        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setToolTip("AutoOCRTranslator")
        icon = self.app.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )
        self.tray_icon.setIcon(icon)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        return True

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """处理托盘图标激活事件."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()

    def run(self) -> int:
        """运行应用主循环.

        Returns:
            应用程序退出码.
        """
        try:
            self.init()
        except Exception as e:
            logger.exception("应用初始化失败")
            QMessageBox.critical(None, "初始化失败", f"应用初始化失败:\n{e}")
            return 1

        if not self._setup_tray_icon():
            logger.info("系统托盘不可用，使用窗口模式")

        return self.app.exec()


def main() -> int:
    """程序入口."""
    app = App()
    return app.run()
