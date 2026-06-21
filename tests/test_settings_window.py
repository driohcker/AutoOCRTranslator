"""设置界面测试."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.config import config
from src.gui.settings_window import SettingsWindow


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestSettingsWindow(unittest.TestCase):
    """SettingsWindow 测试."""

    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()
        cls.original_config_path = config._config_path
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.tmp_config_path = Path(cls.tmp_dir.name) / "settings.yaml"
        shutil.copy(cls.original_config_path, cls.tmp_config_path)
        config._config_path = cls.tmp_config_path

    @classmethod
    def tearDownClass(cls):
        config._config_path = cls.original_config_path
        config.load()
        cls.tmp_dir.cleanup()

    def setUp(self) -> None:
        """每个测试前重新加载临时配置."""
        config.load()

    def test_load_config(self) -> None:
        """测试设置窗口正确加载配置."""
        config.set("translate.source_lang", "en")
        config.set("translate.target_lang", "zh-CN")
        config.set("capture.interval_ms", 2000)
        config.save()

        config.load()
        window = SettingsWindow()
        self.assertEqual(window.source_lang.text(), "en")
        self.assertEqual(window.target_lang.text(), "zh-CN")
        self.assertEqual(window.interval_ms.value(), 2000)

    def test_save_config(self) -> None:
        """测试保存配置到文件."""
        window = SettingsWindow()
        window.source_lang.setText("ja")
        window.target_lang.setText("zh-TW")
        window.interval_ms.setValue(2500)
        window.ocr_lang.setCurrentText("ch")
        window.font_size.setValue(24)
        window.save_config()

        config.load()
        self.assertEqual(config.get("translate.source_lang"), "ja")
        self.assertEqual(config.get("translate.target_lang"), "zh-TW")
        self.assertEqual(config.get("capture.interval_ms"), 2500)
        self.assertEqual(config.get("ocr.lang"), "ch")
        self.assertEqual(config.get("overlay.font_size"), 24)

    @patch("src.gui.settings_window.QMessageBox.information")
    @patch("src.gui.settings_window.Translator")
    def test_test_translation_success(
        self, mock_translator_cls: MagicMock, mock_info: MagicMock
    ) -> None:
        """测试翻译测试按钮成功场景."""
        mock_translator_cls.return_value.translate.return_value = "你好"

        window = SettingsWindow()
        window.provider_combo.setCurrentText("google_free")
        window._test_translation()

        mock_translator_cls.assert_called_once_with(provider_name="google_free")
        mock_info.assert_called_once()

    @patch("src.gui.settings_window.QMessageBox.warning")
    @patch("src.gui.settings_window.Translator")
    def test_test_translation_failure(
        self, mock_translator_cls: MagicMock, mock_warning: MagicMock
    ) -> None:
        """测试翻译测试按钮失败场景."""
        mock_translator_cls.return_value.translate.side_effect = Exception(
            "network error"
        )

        window = SettingsWindow()
        window._test_translation()

        mock_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
