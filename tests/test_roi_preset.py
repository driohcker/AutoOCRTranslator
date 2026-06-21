"""ROI 预设单元测试."""

import unittest

from src.utils.image_roi import ROI_PRESETS, get_roi_from_preset


class TestROIPreset(unittest.TestCase):
    """测试 ROI 预设解析."""

    def test_get_roi_from_preset(self):
        """测试各预设返回正确 ROI."""
        self.assertEqual(
            get_roi_from_preset("subtitle"), ROI_PRESETS["subtitle"]
        )
        self.assertEqual(get_roi_from_preset("bottom"), ROI_PRESETS["bottom"])
        self.assertEqual(get_roi_from_preset("full"), ROI_PRESETS["full"])

    def test_get_roi_from_custom(self):
        """测试自定义 ROI."""
        custom = [0.2, 0.3, 0.5, 0.4]
        self.assertEqual(get_roi_from_preset("custom", custom), custom)

    def test_get_roi_from_unknown(self):
        """测试未知预设回退到字幕预设."""
        self.assertEqual(get_roi_from_preset("unknown"), ROI_PRESETS["subtitle"])


if __name__ == "__main__":
    unittest.main()
