"""语言过滤单元测试."""

import unittest

from src.translate.lang_filter import is_source_lang, should_translate


class TestLangFilter(unittest.TestCase):
    """测试语言过滤工具."""

    def test_is_source_lang_ja(self):
        """测试日文识别：包含假名应识别为日文."""
        self.assertTrue(is_source_lang("こんにちは", "ja"))
        self.assertTrue(is_source_lang("カタカナ", "ja"))
        self.assertTrue(is_source_lang("これは日本語です", "ja"))

    def test_is_source_lang_ja_rejects_chinese(self):
        """测试日文识别：纯中文汉字不应被识别为日文."""
        self.assertFalse(is_source_lang("中文汉字", "ja"))

    def test_is_source_lang_zh(self):
        """测试中文识别."""
        self.assertTrue(is_source_lang("中文汉字", "zh-CN"))
        self.assertTrue(is_source_lang("這是繁體中文", "zh-TW"))

    def test_is_source_lang_en(self):
        """测试英文识别."""
        self.assertTrue(is_source_lang("Hello World", "en"))
        self.assertFalse(is_source_lang("こんにちは", "en"))

    def test_should_translate_filters_url(self):
        """测试 URL 过滤."""
        self.assertFalse(should_translate("https://example.com", "ja"))
        self.assertFalse(should_translate("www.example.com", "ja"))

    def test_should_translate_filters_numbers(self):
        """测试纯数字过滤."""
        self.assertFalse(should_translate("123456", "ja"))
        self.assertFalse(should_translate("2024/01/01", "ja"))

    def test_should_translate_filters_obvious_english(self):
        """测试日文场景下明显英文被过滤."""
        self.assertFalse(should_translate("Settings", "ja"))
        self.assertFalse(should_translate("Click Here", "ja"))

    def test_should_translate_accepts_japanese_kanji(self):
        """测试日文场景下日文汉字被放行."""
        self.assertTrue(should_translate("日本語", "ja"))
        # 非严格模式下放行纯日文汉字
        self.assertTrue(should_translate("東京", "ja", strict=False))

    def test_should_translate_strict_filters_chinese(self):
        """测试严格模式下日文只翻译含假名文本，中文被过滤."""
        self.assertTrue(should_translate("こんにちは", "ja", strict=True))
        self.assertTrue(should_translate("これは日本語です", "ja", strict=True))
        # 严格模式下纯汉字被过滤（避免中文 UI 被误译）
        self.assertFalse(should_translate("中文汉字", "ja", strict=True))
        self.assertFalse(should_translate("東京", "ja", strict=True))

    def test_should_translate_accepts_japanese(self):
        """测试日文文本通过过滤."""
        self.assertTrue(should_translate("こんにちは", "ja"))
        self.assertTrue(should_translate("これはテストです", "ja"))

    def test_should_translate_min_length(self):
        """测试最小长度过滤."""
        self.assertFalse(should_translate("あ", "ja", min_length=3))
        self.assertTrue(should_translate("こんにちは", "ja", min_length=3))


if __name__ == "__main__":
    unittest.main()
