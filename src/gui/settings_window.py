"""设置界面.

提供图形化配置界面，支持修改翻译、OCR、截图、覆盖层等参数.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config import config
from src.gui.zone_selector import Zone, ZoneSelector
from src.translate.translator import Translator


ROI_PRESET_LABELS = {
    "subtitle": "字幕/对话",
    "bottom": "底部全宽",
    "full": "全屏",
    "custom": "自定义",
    "custom_zones": "自定义区域划分",
}
ROI_LABEL_TO_PRESET = {v: k for k, v in ROI_PRESET_LABELS.items()}


class SettingsWindow(QDialog):
    """设置窗口."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AutoOCRTranslator 设置")
        self.resize(520, 620)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        """设置界面布局."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # 滚动区域：放置所有设置分组
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 翻译设置
        trans_group = QGroupBox("翻译")
        trans_layout = QFormLayout()

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(
            ["google_free", "deep_l", "tencent", "aliyun"]
        )
        self.provider_combo.currentTextChanged.connect(
            self._on_provider_changed
        )
        trans_layout.addRow("翻译提供者:", self.provider_combo)

        self.source_lang = QLineEdit()
        trans_layout.addRow("源语言:", self.source_lang)

        self.target_lang = QLineEdit()
        trans_layout.addRow("目标语言:", self.target_lang)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_label = QLabel("API Key:")
        trans_layout.addRow(self.api_key_label, self.api_key)

        self.api_secret = QLineEdit()
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret_label = QLabel("API Secret:")
        trans_layout.addRow(self.api_secret_label, self.api_secret)

        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("如 http://127.0.0.1:7890（仅 Google 免费翻译需要）")
        self.proxy_label = QLabel("HTTP 代理:")
        trans_layout.addRow(self.proxy_label, self.proxy)

        self.filter_source_lang = QCheckBox("只翻译源语言文本（过滤 URL、英文 UI 等）")
        trans_layout.addRow(self.filter_source_lang)

        self.strict_source_lang = QCheckBox(
            "严格过滤（日文只翻译含假名文本，避免中文 UI 被误译）"
        )
        self.strict_source_lang.setToolTip(
            "开启后，日文源语言下只翻译包含平假名/片假名的句子，"
            "避免把中文界面汉字误判为日文。关闭则放行日文汉字。"
        )
        trans_layout.addRow(self.strict_source_lang)

        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        # OCR 设置
        ocr_group = QGroupBox("OCR")
        ocr_layout = QFormLayout()

        self.ocr_engine = QComboBox()
        self.ocr_engine.addItems(["rapid", "paddle"])
        self.ocr_engine.currentTextChanged.connect(
            self._on_ocr_engine_changed
        )
        ocr_layout.addRow("OCR 引擎:", self.ocr_engine)

        self.use_gpu = QCheckBox("启用 GPU 加速 OCR (实验性)")
        self.use_gpu.setToolTip(
            "对 RapidOCR/PaddleOCR 均有效。RapidOCR 需要安装 onnxruntime-gpu 补丁；"
            "PaddleOCR 需要安装 paddlepaddle-gpu 补丁。开启后保存设置，"
            "翻译循环会自动重启。"
        )
        ocr_layout.addRow(self.use_gpu)

        self.ocr_lang = QComboBox()
        self.ocr_lang.addItems(["japan", "ch", "ch_tra", "en"])
        ocr_layout.addRow("OCR 语言:", self.ocr_lang)

        self.drop_score = QDoubleSpinBox()
        self.drop_score.setRange(0.0, 1.0)
        self.drop_score.setSingleStep(0.05)
        self.drop_score.setDecimals(2)
        ocr_layout.addRow("置信度阈值:", self.drop_score)

        self.ocr_max_width = QSpinBox()
        self.ocr_max_width.setRange(0, 1920)
        self.ocr_max_width.setSingleStep(50)
        self.ocr_max_width.setSpecialValueText("不缩放")
        ocr_layout.addRow("OCR 最大宽度(0=不缩放):", self.ocr_max_width)

        self.det_limit_side_len = QSpinBox()
        self.det_limit_side_len.setRange(160, 1920)
        self.det_limit_side_len.setSingleStep(50)
        ocr_layout.addRow("检测最长边限制:", self.det_limit_side_len)

        self.roi_preset = QComboBox()
        self.roi_preset.addItems(
            ["字幕/对话", "底部全宽", "全屏", "自定义", "自定义区域划分"]
        )
        self.roi_preset.currentTextChanged.connect(self._on_roi_preset_changed)
        ocr_layout.addRow("OCR 区域预设:", self.roi_preset)

        # 原有手动输入自定义区域
        roi_layout = QHBoxLayout()
        self.roi_x = QDoubleSpinBox()
        self.roi_y = QDoubleSpinBox()
        self.roi_w = QDoubleSpinBox()
        self.roi_h = QDoubleSpinBox()
        for spin in (self.roi_x, self.roi_y, self.roi_w, self.roi_h):
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            roi_layout.addWidget(spin)
        self._roi_spin_layout = roi_layout
        self._roi_spin_label = QLabel("自定义区域 [x,y,w,h]:")
        ocr_layout.addRow(self._roi_spin_label, roi_layout)

        # 新增“自定义区域划分”控件
        zones_layout = QHBoxLayout()
        self._zones_label = QLabel("已划分 0 个区域")
        self._zones_button = QPushButton("划分区域")
        self._zones_button.setToolTip("在目标窗口上拖拽画出翻译区域")
        self._zones_button.clicked.connect(self._open_zone_selector)
        zones_layout.addWidget(self._zones_label)
        zones_layout.addWidget(self._zones_button)
        zones_layout.addStretch()
        self._zones_widget = QWidget()
        self._zones_widget.setLayout(zones_layout)
        ocr_layout.addRow(self._zones_widget)

        ocr_group.setLayout(ocr_layout)
        layout.addWidget(ocr_group)

        # 截图设置
        cap_group = QGroupBox("截图")
        cap_layout = QFormLayout()

        self.interval_ms = QSpinBox()
        self.interval_ms.setRange(100, 10000)
        self.interval_ms.setSingleStep(100)
        cap_layout.addRow("截图间隔(ms):", self.interval_ms)

        cap_group.setLayout(cap_layout)
        layout.addWidget(cap_group)

        # 覆盖层设置
        overlay_group = QGroupBox("覆盖层")
        overlay_layout = QFormLayout()

        self.font_family = QLineEdit()
        overlay_layout.addRow("字体:", self.font_family)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        overlay_layout.addRow("字号:", self.font_size)

        self.font_color = QLineEdit()
        overlay_layout.addRow("字体颜色(如 #FFFFFF):", self.font_color)

        self.bg_color = QLineEdit()
        overlay_layout.addRow("背景颜色(如 #80000000):", self.bg_color)

        self.max_width = QSpinBox()
        self.max_width.setRange(50, 2000)
        overlay_layout.addRow("最大宽度:", self.max_width)

        overlay_group.setLayout(overlay_layout)
        layout.addWidget(overlay_group)

        # 悬浮日志设置
        log_group = QGroupBox("悬浮日志窗口")
        log_layout = QFormLayout()

        self.log_overlay_enabled = QCheckBox("启用悬浮日志窗口")
        log_layout.addRow(self.log_overlay_enabled)

        self.log_overlay_width = QSpinBox()
        self.log_overlay_width.setRange(200, 1920)
        self.log_overlay_width.setSingleStep(50)
        log_layout.addRow("宽度:", self.log_overlay_width)

        self.log_overlay_height = QSpinBox()
        self.log_overlay_height.setRange(150, 1080)
        self.log_overlay_height.setSingleStep(50)
        log_layout.addRow("高度:", self.log_overlay_height)

        self.log_overlay_opacity = QDoubleSpinBox()
        self.log_overlay_opacity.setRange(0.1, 1.0)
        self.log_overlay_opacity.setSingleStep(0.05)
        self.log_overlay_opacity.setDecimals(2)
        log_layout.addRow("透明度:", self.log_overlay_opacity)

        self.log_overlay_font_size = QSpinBox()
        self.log_overlay_font_size.setRange(8, 32)
        log_layout.addRow("字体大小:", self.log_overlay_font_size)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 底部按钮：始终固定在对话框底部
        btn_layout = QHBoxLayout()
        self.btn_test = QPushButton("测试翻译")
        self.btn_save = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addWidget(self.btn_test)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

        self.btn_test.clicked.connect(self._test_translation)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)

    def _load_config(self) -> None:
        """从配置文件加载当前值到界面."""
        self.provider_combo.setCurrentText(
            config.get("translate.provider", "google_free")
        )
        self.source_lang.setText(config.get("translate.source_lang", "ja"))
        self.target_lang.setText(config.get("translate.target_lang", "zh-CN"))
        self.api_key.setText(config.get("translate.api_key", ""))
        self.api_secret.setText(config.get("translate.api_secret", ""))
        self.proxy.setText(config.get("translate.proxy", ""))
        self.filter_source_lang.setChecked(
            config.get("translate.filter_source_lang", True)
        )
        self.strict_source_lang.setChecked(
            config.get("translate.strict_source_lang", True)
        )

        self.ocr_engine.setCurrentText(config.get("ocr.engine", "rapid"))
        self.use_gpu.setChecked(config.get("ocr.use_gpu", False))
        self.ocr_lang.setCurrentText(config.get("ocr.lang", "japan"))
        self.drop_score.setValue(config.get("ocr.drop_score", 0.7))
        self.ocr_max_width.setValue(config.get("ocr.max_width", 480))
        self.det_limit_side_len.setValue(
            config.get("ocr.det_limit_side_len", 480)
        )

        preset = config.get("ocr.roi_preset", "subtitle")
        self.roi_preset.setCurrentText(
            ROI_PRESET_LABELS.get(preset, "字幕/对话")
        )

        roi_custom = config.get("ocr.roi_custom", [0.1, 0.75, 0.8, 0.2])
        if roi_custom and len(roi_custom) == 4:
            self.roi_x.setValue(roi_custom[0])
            self.roi_y.setValue(roi_custom[1])
            self.roi_w.setValue(roi_custom[2])
            self.roi_h.setValue(roi_custom[3])

        self._roi_zones: List[Zone] = list(config.get("ocr.roi_zones", []) or [])
        self._update_zones_label()

        self._on_roi_preset_changed()

        self.interval_ms.setValue(config.get("capture.interval_ms", 5000))

        self.font_family.setText(
            config.get("overlay.font_family", "Microsoft YaHei")
        )
        self.font_size.setValue(config.get("overlay.font_size", 18))
        self.font_color.setText(config.get("overlay.font_color", "#FFFFFF"))
        self.bg_color.setText(config.get("overlay.bg_color", "#80000000"))
        self.max_width.setValue(config.get("overlay.max_width", 400))

        self.log_overlay_enabled.setChecked(
            config.get("log_overlay.enabled", False)
        )
        self.log_overlay_width.setValue(
            config.get("log_overlay.width", 420)
        )
        self.log_overlay_height.setValue(
            config.get("log_overlay.height", 320)
        )
        self.log_overlay_opacity.setValue(
            config.get("log_overlay.opacity", 0.85)
        )
        self.log_overlay_font_size.setValue(
            config.get("log_overlay.font_size", 12)
        )

        self._on_provider_changed()

    def _on_provider_changed(self) -> None:
        """根据所选翻译提供者更新凭证输入框标签."""
        provider = self.provider_combo.currentText()
        if provider == "tencent":
            self.api_key_label.setText("SecretId:")
            self.api_secret_label.setText("SecretKey:")
            self.api_secret_label.setVisible(True)
            self.api_secret.setVisible(True)
            self.proxy_label.setVisible(False)
            self.proxy.setVisible(False)
        elif provider == "deep_l":
            self.api_key_label.setText("Auth Key:")
            self.api_secret_label.setVisible(False)
            self.api_secret.setVisible(False)
            self.proxy_label.setVisible(True)
            self.proxy.setVisible(True)
        elif provider == "aliyun":
            self.api_key_label.setText("AccessKey ID:")
            self.api_secret_label.setText("AccessKey Secret:")
            self.api_secret_label.setVisible(True)
            self.api_secret.setVisible(True)
            self.proxy_label.setVisible(False)
            self.proxy.setVisible(False)
        else:  # google_free
            self.api_key_label.setText("API Key:")
            self.api_secret_label.setVisible(False)
            self.api_secret.setVisible(False)
            self.proxy_label.setVisible(True)
            self.proxy.setVisible(True)

    def _on_save(self) -> None:
        """保存界面配置到文件."""
        if self.save_config():
            self.accept()

    def save_config(self) -> bool:
        """将界面当前值写入配置文件.

        Returns:
            保存成功返回 True，失败返回 False。
        """
        try:
            self._do_save_config()
            return True
        except Exception as e:
            logger.exception("保存配置失败")
            QMessageBox.critical(self, "保存失败", f"保存配置时出错:\n{e}")
            return False

    def _do_save_config(self) -> None:
        """实际保存配置到文件."""
        config.set("translate.provider", self.provider_combo.currentText())
        config.set("translate.source_lang", self.source_lang.text())
        config.set("translate.target_lang", self.target_lang.text())
        config.set("translate.api_key", self.api_key.text())
        config.set("translate.api_secret", self.api_secret.text())
        config.set("translate.proxy", self.proxy.text())
        config.set(
            "translate.filter_source_lang", self.filter_source_lang.isChecked()
        )
        config.set(
            "translate.strict_source_lang", self.strict_source_lang.isChecked()
        )

        config.set("ocr.engine", self.ocr_engine.currentText())
        config.set("ocr.use_gpu", self.use_gpu.isChecked())
        config.set("ocr.lang", self.ocr_lang.currentText())
        config.set("ocr.drop_score", self.drop_score.value())
        config.set("ocr.max_width", self.ocr_max_width.value())
        config.set(
            "ocr.det_limit_side_len", self.det_limit_side_len.value()
        )

        preset = ROI_LABEL_TO_PRESET.get(
            self.roi_preset.currentText(), "subtitle"
        )
        config.set("ocr.roi_preset", preset)
        config.set(
            "ocr.roi_custom",
            [
                self.roi_x.value(),
                self.roi_y.value(),
                self.roi_w.value(),
                self.roi_h.value(),
            ],
        )
        config.set("ocr.roi_zones", [list(z) for z in self._roi_zones])

        config.set("capture.interval_ms", self.interval_ms.value())

        config.set("overlay.font_family", self.font_family.text())
        config.set("overlay.font_size", self.font_size.value())
        config.set("overlay.font_color", self.font_color.text())
        config.set("overlay.bg_color", self.bg_color.text())
        config.set("overlay.max_width", self.max_width.value())

        config.set(
            "log_overlay.enabled", self.log_overlay_enabled.isChecked()
        )
        config.set("log_overlay.width", self.log_overlay_width.value())
        config.set("log_overlay.height", self.log_overlay_height.value())
        config.set(
            "log_overlay.opacity", self.log_overlay_opacity.value()
        )
        config.set(
            "log_overlay.font_size", self.log_overlay_font_size.value()
        )

        config.save()

    def _on_roi_preset_changed(self, text: str = "") -> None:
        """ROI 预设变化时启用/禁用对应输入控件."""
        preset = ROI_LABEL_TO_PRESET.get(self.roi_preset.currentText(), "subtitle")
        is_custom = preset == "custom"
        is_zones = preset == "custom_zones"

        for spin in (self.roi_x, self.roi_y, self.roi_w, self.roi_h):
            spin.setEnabled(is_custom)
        self._roi_spin_label.setEnabled(is_custom)

        self._zones_widget.setVisible(is_zones)

    def _on_ocr_engine_changed(self, text: str = "") -> None:
        """OCR 引擎变化时更新 GPU 选项提示（现在 RapidOCR 也支持 GPU）."""
        # RapidOCR 与 PaddleOCR 都可以通过安装对应 GPU 补丁启用加速，
        # 因此 GPU 复选框始终保持可用。
        pass

    def _update_zones_label(self) -> None:
        """更新已划分区域数量显示."""
        count = len(self._roi_zones)
        self._zones_label.setText(f"已划分 {count} 个区域")

    def _open_zone_selector(self) -> None:
        """打开区域划分选择器.

        打开前先隐藏本程序的主窗口和设置窗口，避免它们遮挡目标程序，
        同时保证截图中不会包含本程序界面。
        """
        controller = getattr(self.parent(), "controller", None)
        capture = getattr(controller, "capture", None)
        if capture is None:
            QMessageBox.warning(self, "提示", "无法获取截图模块，请重试。")
            return

        if not capture.is_valid():
            QMessageBox.information(
                self, "提示", "请先选择目标窗口，再进行区域划分。"
            )
            return

        # 最小化本程序窗口，避免遮挡目标程序
        main_window = self.parent()
        self.showMinimized()
        if main_window is not None:
            main_window.showMinimized()

        # 给目标窗口一点重绘时间，然后截图
        from PyQt6.QtCore import QTimer

        def do_capture() -> None:
            screenshot = capture.capture()
            rect = capture.get_client_rect()

            if screenshot is None or rect is None:
                # 先恢复窗口，再提示，避免消息框被遮挡
                self.showNormal()
                if main_window is not None:
                    main_window.showNormal()
                QMessageBox.warning(self, "提示", "截图失败，请确认目标窗口可见。")
                return

            # parent 为 SettingsWindow，但 SettingsWindow 已最小化，不会遮挡
            selector = ZoneSelector(
                background_image=screenshot,
                screen_rect=rect,
                existing_zones=self._roi_zones,
                parent=self,
            )
            zones = selector.select()
            logger.info(f"ZoneSelector 返回: {zones}")
            if zones is not None:
                self._roi_zones = zones
                logger.info(f"设置窗口 _roi_zones 已更新: {self._roi_zones}")
                self._update_zones_label()
            else:
                logger.info("用户取消区域划分，未更新 _roi_zones")

            # 恢复本程序窗口
            self.showNormal()
            if main_window is not None:
                main_window.showNormal()
                main_window.raise_()
                main_window.activateWindow()
            self.raise_()
            self.activateWindow()

        # 延迟 300ms 截图，确保目标窗口已完全显示
        QTimer.singleShot(300, do_capture)

    def _test_translation(self) -> None:
        """测试当前翻译配置是否可用."""
        provider = self.provider_combo.currentText()
        source = self.source_lang.text()
        target = self.target_lang.text()

        try:
            translator = Translator(provider_name=provider)
            result = translator.translate("hello", source, target)
            if result:
                QMessageBox.information(
                    self, "测试成功", f"翻译结果:\n{result}"
                )
            else:
                QMessageBox.warning(
                    self, "测试失败", "翻译结果为空，请检查配置。"
                )
        except Exception as e:
            QMessageBox.warning(self, "测试失败", str(e))
