"""窗口捕获模块测试."""

import os
import unittest

from PIL import Image

from src.capture.window_capture import (
    WindowCapture,
    WindowCaptureError,
    select_window_dialog,
)


class TestWindowCapture(unittest.TestCase):
    """WindowCapture 单元测试."""

    def test_list_windows_returns_valid_list(self):
        """测试枚举窗口返回合法的窗口列表."""
        windows = WindowCapture.list_windows()
        self.assertIsInstance(windows, list)
        self.assertGreater(len(windows), 0, "当前应至少有一个可见窗口")

        for hwnd, title in windows:
            self.assertIsInstance(hwnd, int)
            self.assertIsInstance(title, str)
            self.assertTrue(title.strip(), "窗口标题不应为空")

    def test_find_window_by_keyword(self):
        """测试按关键词查找窗口."""
        capture = WindowCapture()
        # 使用常见窗口标题关键词测试, 未找到也不报错
        result = capture.find_window("Visual Studio Code")
        if result is None:
            result = capture.find_window("AutoOCRTranslator")

        if result is not None:
            hwnd, title = result
            self.assertIsInstance(hwnd, int)
            self.assertIsInstance(title, str)
            self.assertTrue(hwnd > 0)

    def test_set_target_with_invalid_hwnd_raises(self):
        """测试设置无效窗口句柄应抛出异常."""
        capture = WindowCapture()
        with self.assertRaises(WindowCaptureError):
            capture.set_target(0)

    def test_is_valid_without_target(self):
        """测试未设置目标时窗口无效."""
        capture = WindowCapture()
        self.assertIsNone(capture.get_target())
        self.assertFalse(capture.is_valid())
        self.assertIsNone(capture.capture())

    def test_capture_real_window(self):
        """测试对真实窗口截图.

        如果当前存在 Visual Studio Code 或 AutoOCRTranslator 窗口,
        则截取并保存为测试图片供手动检查.
        """
        capture = WindowCapture()

        candidates = ["Visual Studio Code", "AutoOCRTranslator", "Windows PowerShell"]
        target = None
        for keyword in candidates:
            target = capture.find_window(keyword)
            if target is not None:
                break

        if target is None:
            self.skipTest("未找到可用于截图的测试窗口")

        hwnd, title = target
        capture.set_target(hwnd)
        self.assertTrue(capture.is_valid(), f"窗口应有效: {title}")

        rect = capture.get_client_rect()
        self.assertIsNotNone(rect)

        img = capture.capture()
        self.assertIsInstance(img, Image.Image)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

        output_path = "tests/capture_test_output.png"
        img.save(output_path)
        print(f"已保存测试截图: {output_path} ({img.width}x{img.height})")
        self.assertTrue(os.path.exists(output_path))


class TestSelectWindowDialog(unittest.TestCase):
    """窗口选择对话框测试 (仅验证无异常)."""

    def test_select_window_dialog_with_empty_list(self):
        """测试空列表传入对话框不崩溃."""
        # 不实际弹出对话框, 只在空列表时验证返回 None
        result = select_window_dialog([])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
