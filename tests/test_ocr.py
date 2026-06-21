"""OCR 模块测试."""

import os
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.ocr.paddle_ocr import PaddleOCREngine


TEST_IMAGE_PATH = Path("tests/ocr_test_input2.png")


def _ensure_test_image() -> Path:
    """创建或复用测试图片."""
    if TEST_IMAGE_PATH.exists():
        return TEST_IMAGE_PATH

    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)

    fonts_to_try = ["msgothic.ttc", "msmincho.ttc", "YuGothM.ttc", "meiryo.ttc"]
    font = None
    for ft in fonts_to_try:
        try:
            font = ImageFont.truetype(ft, 48)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    draw.text((50, 60), "こんにちは", fill="black", font=font)
    draw.text((350, 60), "Hello World", fill="black", font=font)
    draw.text((600, 60), "你好", fill="black", font=font)

    TEST_IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(TEST_IMAGE_PATH)
    return TEST_IMAGE_PATH


class TestPaddleOCREngine(unittest.TestCase):
    """PaddleOCR 引擎测试."""

    @classmethod
    def setUpClass(cls):
        """测试类开始时初始化 OCR 引擎（模型只加载一次）."""
        cls.ocr = PaddleOCREngine(
            lang="japan",
            use_gpu=False,
            drop_score=0.5,
        )
        cls.image_path = _ensure_test_image()
        cls.image = Image.open(cls.image_path)

    def test_normalize_lang(self):
        """测试语言名称标准化."""
        engine = PaddleOCREngine(lang="ja", use_gpu=False)
        self.assertEqual(engine.lang, "japan")

        engine = PaddleOCREngine(lang="zh", use_gpu=False)
        self.assertEqual(engine.lang, "ch")

        engine = PaddleOCREngine(lang="en", use_gpu=False)
        self.assertEqual(engine.lang, "en")

    def test_recognize_returns_list(self):
        """测试 recognize 返回列表."""
        results = self.ocr.recognize(self.image)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_recognize_result_format(self):
        """测试识别结果格式正确."""
        results = self.ocr.recognize(self.image)
        for item in results:
            self.assertIn("text", item)
            self.assertIn("box", item)
            self.assertIn("score", item)
            self.assertIsInstance(item["text"], str)
            self.assertIsInstance(item["box"], list)
            self.assertEqual(len(item["box"]), 4)
            self.assertGreaterEqual(item["score"], self.ocr.drop_score)

    def test_recognize_japanese(self):
        """测试能识别日文文本."""
        results = self.ocr.recognize(self.image)
        texts = [r["text"] for r in results]
        # 由于字体和模型原因，可能无法完全匹配，至少应识别出部分内容
        self.assertTrue(
            any("こん" in t or "にち" in t or "は" in t for t in texts),
            f"未识别出日文问候语，实际结果: {texts}",
        )

    def test_recognize_english(self):
        """测试能识别英文文本."""
        results = self.ocr.recognize(self.image)
        texts = [r["text"].lower() for r in results]
        self.assertTrue(
            any("hello" in t or "world" in t for t in texts),
            f"未识别出英文文本，实际结果: {texts}",
        )

    def test_recognize_none_image(self):
        """测试传入 None 返回空列表."""
        results = self.ocr.recognize(None)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
