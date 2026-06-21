"""主控制窗口.

提供美观、持续可见的 GUI 控制界面, 包括状态显示、控制按钮、
实时日志、最近识别文本、缓存统计等功能.
"""

import logging
import weakref
from typing import Any, Dict, List, Optional

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt6 import sip
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import config
from src.gui.settings_window import SettingsWindow


class LogSignal(logging.Handler):
    """自定义日志处理器，将日志发送到 GUI."""

    def __init__(self, window: "MainWindow"):
        super().__init__()
        # 弱引用避免阻止窗口回收；窗口销毁后自动停止发送信号
        self._window_ref = weakref.ref(window)

    def emit(self, record: logging.LogRecord) -> None:
        window = self._window_ref()
        # 窗口已销毁或无 GUI 事件循环时不发送信号
        if window is None or QApplication.instance() is None:
            return
        # 只允许主线程的日志进入 GUI，避免工作线程跨线程访问 QObject。
        # 工作线程的日志仍会通过根记录器的其他 handler 输出到文件/控制台。
        if QThread.currentThread() != QApplication.instance().thread():
            return
        # 防止窗口底层 C++ 对象已被销毁后仍访问其信号
        if sip.isdeleted(window):
            return
        try:
            msg = self.format(record)
            window.log_signal.emit(msg)
        except Exception:
            self.handleError(record)


class StatusIndicator(QWidget):
    """彩色状态指示灯."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor("#808080")  # 默认灰色

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(self._color.darker(120))
        painter.drawEllipse(0, 0, self.width() - 1, self.height() - 1)


class MainWindow(QMainWindow):
    """应用主控制窗口."""

    log_signal = pyqtSignal(str)

    def __init__(self, app_controller: Any, parent=None) -> None:
        super().__init__(parent)
        self.controller = app_controller
        self._ocr_preview_images: List[Image.Image] = []
        self._preview_resize_timer = QTimer(self)
        self._preview_resize_timer.setSingleShot(True)
        self._preview_resize_timer.timeout.connect(self._render_ocr_preview)
        self._setup_window()
        self._setup_ui()
        self._setup_styles()
        self._setup_logging()
        self._update_ui_state()

    def _setup_window(self) -> None:
        """设置窗口基本属性."""
        self.setWindowTitle("AutoOCRTranslator")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

    def _setup_ui(self) -> None:
        """设置界面布局."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("AutoOCRTranslator")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 状态卡片
        status_card = QGroupBox("当前状态")
        status_layout = QHBoxLayout(status_card)
        status_layout.setSpacing(20)

        self.status_indicator = StatusIndicator()
        self.status_text = QLabel("已停止")
        self.status_text.setObjectName("statusText")

        self.target_label = QLabel("目标窗口: 未选择")
        self.target_label.setObjectName("targetLabel")

        self.interval_label = QLabel("截图间隔: 1000ms")
        self.interval_label.setObjectName("intervalLabel")

        self.performance_label = QLabel("最近 OCR: --")
        self.performance_label.setObjectName("performanceLabel")

        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        status_layout.addWidget(self.target_label)
        status_layout.addWidget(self.interval_label)
        status_layout.addWidget(self.performance_label)
        main_layout.addWidget(status_card)

        # 控制按钮区
        control_card = QGroupBox("控制")
        control_layout = QHBoxLayout(control_card)
        control_layout.setSpacing(12)

        self.btn_select = QPushButton("选择窗口")
        self.btn_select.setObjectName("primaryButton")
        self.btn_select.clicked.connect(self._on_select_window)

        self.btn_toggle = QPushButton("开始翻译")
        self.btn_toggle.setObjectName("primaryButton")
        self.btn_toggle.clicked.connect(self._on_toggle_translation)

        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self._on_settings)

        self.btn_clear_cache = QPushButton("清空缓存")
        self.btn_clear_cache.clicked.connect(self._on_clear_cache)

        self.btn_log_overlay = QPushButton("悬浮日志")
        self.btn_log_overlay.setCheckable(True)
        self.btn_log_overlay.clicked.connect(self._on_toggle_log_overlay)

        control_layout.addWidget(self.btn_select)
        control_layout.addWidget(self.btn_toggle)
        control_layout.addWidget(self.btn_settings)
        control_layout.addWidget(self.btn_log_overlay)
        control_layout.addStretch()
        control_layout.addWidget(self.btn_clear_cache)
        main_layout.addWidget(control_card)

        # 下部标签页
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：实时日志
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_group)

        # 右侧：标签页
        right_tabs = QTabWidget()

        # OCR 预览
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.ocr_preview_scroll = QScrollArea()
        self.ocr_preview_scroll.setWidgetResizable(True)
        self.ocr_preview_scroll.setStyleSheet(
            "QScrollArea { background-color: #2c3e50; border: none; }"
        )
        self.ocr_preview_container = QWidget()
        self.ocr_preview_layout = QGridLayout(self.ocr_preview_container)
        self.ocr_preview_layout.setSpacing(8)
        self.ocr_preview_layout.setContentsMargins(8, 8, 8, 8)
        self.ocr_preview_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.ocr_preview_scroll.setWidget(self.ocr_preview_container)
        preview_layout.addWidget(self.ocr_preview_scroll)
        self._show_ocr_preview_placeholder("等待 OCR...")
        right_tabs.addTab(preview_tab, "OCR 预览")

        # 最近识别
        recent_tab = QWidget()
        recent_layout = QVBoxLayout(recent_tab)
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(3)
        self.recent_table.setHorizontalHeaderLabels(["原文", "译文", "置信度"])
        self.recent_table.horizontalHeader().setStretchLastSection(False)
        self.recent_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.recent_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.recent_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.recent_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        recent_layout.addWidget(self.recent_table)
        right_tabs.addTab(recent_tab, "最近识别")

        # 统计信息
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        self.stats_label = QLabel("缓存统计")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        right_tabs.addTab(stats_tab, "统计")

        splitter.addWidget(right_tabs)
        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        self.setStatusBar(self.status_bar)

    def _setup_styles(self) -> None:
        """设置 QSS 样式."""
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f5f6fa;
            }
            #titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #2c3e50;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 6px;
                border: 1px solid #dcdde1;
                background-color: #ffffff;
                color: #2c3e50;
                font-weight: 500;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #f1f2f6;
                border-color: #c8c9cc;
            }
            QPushButton:pressed {
                background-color: #e1e2e6;
            }
            #primaryButton {
                background-color: #3498db;
                color: white;
                border: none;
            }
            #primaryButton:hover {
                background-color: #2980b9;
            }
            #primaryButton:pressed {
                background-color: #1f618d;
            }
            #primaryButton:disabled {
                background-color: #bdc3c7;
            }
            QTextEdit {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                padding: 8px;
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
            QTableWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
                gridline-color: #ecf0f1;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #ecf0f1;
                padding: 8px;
                border: none;
                font-weight: bold;
                color: #2c3e50;
            }
            #statusText {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
            #targetLabel, #intervalLabel, #performanceLabel {
                color: #7f8c8d;
            }
            QTabWidget::pane {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                background-color: #ecf0f1;
                color: #7f8c8d;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #3498db;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #dfe6e9;
            }
            QStatusBar {
                background-color: #ecf0f1;
                color: #7f8c8d;
            }
            """
        )

    def _setup_logging(self) -> None:
        """将日志重定向到 GUI."""
        self.log_signal.connect(self._append_log)
        self._log_handler = LogSignal(self)
        self._log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(self._log_handler)
        self.destroyed.connect(self._remove_log_handler)

    def _remove_log_handler(self) -> None:
        """窗口销毁时移除日志处理器，避免悬空引用."""
        if self._log_handler is not None:
            try:
                logging.getLogger().removeHandler(self._log_handler)
            except Exception:
                pass
            self._log_handler = None

    def _append_log(self, msg: str) -> None:
        """追加日志到文本框."""
        self.log_text.append(msg)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_select_window(self) -> None:
        """选择目标窗口按钮."""
        if self.controller:
            self.controller.select_window()

    def _on_toggle_translation(self) -> None:
        """开始/停止翻译按钮."""
        if not self.controller:
            return
        if self.controller.is_running:
            self.controller.stop()
        else:
            self.controller.start()

    def _on_settings(self) -> None:
        """打开设置窗口."""
        dialog = SettingsWindow(self)
        if dialog.exec() != SettingsWindow.DialogCode.Accepted:
            return

        try:
            config.load()
        except Exception as e:
            logger.exception("重新加载配置失败")
            QMessageBox.critical(self, "配置加载失败", f"重新加载配置时出错:\n{e}")
            return

        if self.controller:
            self.controller._apply_config()

    def _on_clear_cache(self) -> None:
        """清空缓存按钮."""
        if not self.controller or not self.controller.cache:
            QMessageBox.information(self, "提示", "缓存未启用")
            return

        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有翻译缓存吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.cache.clear()
            self.update_stats()
            self.status_bar.showMessage("缓存已清空", 3000)

    def _on_toggle_log_overlay(self) -> None:
        """切换悬浮日志窗口."""
        if not self.controller:
            return
        self.controller.toggle_log_overlay()

    def update_status(self, is_running: bool, target_title: str = "") -> None:
        """更新状态显示."""
        if is_running:
            self.status_text.setText("运行中")
            self.status_indicator.set_color("#27ae60")
            self.btn_toggle.setText("停止翻译")
            self.status_bar.showMessage("翻译循环运行中")
        else:
            self.status_text.setText("已停止")
            self.status_indicator.set_color("#e74c3c")
            self.btn_toggle.setText("开始翻译")
            self.status_bar.showMessage("翻译循环已停止")

        if target_title:
            self.target_label.setText(f"目标窗口: {target_title}")

    def set_ocr_preview(self, images: Any) -> None:
        """在主窗口显示当前 OCR 实际识别的图像.

        支持传入单张 PIL 图像或一个图像列表；一次调用代表一个识别批次，
        会清空之前的预览并用当前批次的所有图片替换。

        Args:
            images: PIL 图像，或 PIL 图像的列表/元组。
        """
        try:
            if isinstance(images, Image.Image):
                images = [images]
            elif isinstance(images, (list, tuple)):
                images = list(images)
            else:
                logger.warning(f"未知的 OCR 预览数据类型: {type(images)}")
                return

            self._ocr_preview_images = images
            self._render_ocr_preview()
        except Exception as e:
            logger.warning(f"更新 OCR 预览图失败: {e}")

    def _render_ocr_preview(self) -> None:
        """根据当前存储的图像列表重新渲染预览网格."""
        self._clear_ocr_preview()
        images = getattr(self, "_ocr_preview_images", [])
        if not images:
            self._show_ocr_preview_placeholder("等待 OCR...")
            return

        viewport = self.ocr_preview_scroll.viewport()
        container_width = viewport.width() if viewport else 0
        if container_width <= 0:
            container_width = self.ocr_preview_scroll.width()
        if container_width <= 0:
            container_width = 400

        target_cell_width = 240
        columns = max(1, container_width // target_cell_width)
        spacing = self.ocr_preview_layout.spacing()
        margins = self.ocr_preview_layout.contentsMargins()
        available_width = (
            container_width
            - margins.left()
            - margins.right()
            - (columns - 1) * spacing
        )
        cell_width = max(160, available_width // columns)
        cell_height = int(cell_width * 0.75)

        for idx, image in enumerate(images):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                "background-color: #34495e; border-radius: 4px;"
            )
            label.setFixedSize(cell_width, cell_height)
            try:
                preview_image = image.copy()
                preview_image.thumbnail(
                    (cell_width, cell_height),
                    Image.Resampling.LANCZOS,
                )
                qt_image = ImageQt(preview_image)
                pixmap = QPixmap.fromImage(qt_image)
                label.setPixmap(pixmap)
            except Exception as e:
                logger.warning(f"加载第 {idx + 1} 张预览图失败: {e}")
                label.setText("图像加载失败")
                label.setStyleSheet(
                    "color: #ecf0f1; background-color: #34495e; border-radius: 4px;"
                )

            row = idx // columns
            col = idx % columns
            self.ocr_preview_layout.addWidget(label, row, col)

    def _clear_ocr_preview(self) -> None:
        """清空 OCR 预览网格中的所有控件."""
        while self.ocr_preview_layout.count():
            item = self.ocr_preview_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_ocr_preview_placeholder(self, text: str) -> None:
        """在 OCR 预览区域显示占位文本."""
        self._clear_ocr_preview()
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #ecf0f1; background-color: transparent;")
        self.ocr_preview_layout.addWidget(label, 0, 0)

    def update_recent(self, items: List[Dict[str, Any]]) -> None:
        """更新最近识别表格."""
        self.recent_table.setRowCount(min(len(items), 50))
        for i, item in enumerate(items[:50]):
            original = item.get("original", "")
            translated = item.get("translated", "")
            score = item.get("score", 0.0)

            self.recent_table.setItem(i, 0, QTableWidgetItem(original))
            self.recent_table.setItem(i, 1, QTableWidgetItem(translated))
            score_item = QTableWidgetItem(f"{score:.2f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.recent_table.setItem(i, 2, score_item)

    def update_stats(self) -> None:
        """更新统计信息."""
        if not self.controller or not self.controller.cache:
            self.stats_label.setText("缓存未启用")
            return

        try:
            stats = self.controller.cache.stats()
            count = int(stats.get("count", 0))
            total_hits = int(stats.get("total_hits", 0))
            avg = total_hits / max(count, 1)
            self.stats_label.setText(
                f"缓存条目数: {count}\n"
                f"总命中次数: {total_hits}\n"
                f"平均命中: {avg:.2f} 次/条"
            )
        except Exception as e:
            self.stats_label.setText(f"缓存统计获取失败: {e}")

    def update_performance(self, elapsed: float, skipped_frames: int) -> None:
        """更新性能信息.

        Args:
            elapsed: 最近一帧 OCR + 翻译耗时（秒）。
            skipped_frames: 自上次完成以来因 OCR 忙而跳过的帧数。
        """
        text = f"最近 OCR: {elapsed:.2f}s"
        if skipped_frames > 0:
            text += f" / 跳过 {skipped_frames} 帧"
        self.performance_label.setText(text)

    def _update_ui_state(self) -> None:
        """根据控制器状态更新 UI."""
        if self.controller:
            self.update_status(
                self.controller.is_running,
                getattr(self.controller, "_target_title", ""),
            )
            self.update_stats()

    def resizeEvent(self, event: Any) -> None:
        """窗口大小变化时重新排列 OCR 预览图."""
        super().resizeEvent(event)
        if self._ocr_preview_images:
            self._preview_resize_timer.start(200)

    def closeEvent(self, event: Any) -> None:
        """关闭事件：直接退出程序，避免用户无法关闭."""
        if self.controller:
            self.controller.quit()
        event.accept()
