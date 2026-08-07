"""ROI 画面变化检测.

对每个已缩放的 ROI 图像计算感知哈希（dHash），若任一区域与上次
差异超过阈值，则判定画面发生变化。用于在 OCR 前挡掉大量无变化帧，
是「便宜优先」管道的第一个闸门（单区域耗时 <1ms）。
"""

import logging
from typing import Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class ChangeDetector:
    """基于 dHash 的区域级变化检测器.

    用法：每帧对每个 zone 调用 check()，返回 True 表示画面有变化；
    内部会自动维护每个区域的上一次哈希值。
    """

    def __init__(self, threshold: int = 4) -> None:
        self._threshold = max(1, int(threshold))
        self._hashes: Dict[int, int] = {}

    def check(self, images: List[Image.Image]) -> bool:
        """检测 images（与 zone 索引一一对应）相对上次是否有变化."""
        changed = False
        new_hashes: Dict[int, int] = {}
        for idx, image in enumerate(images):
            if image is None:
                continue
            h = self._dhash(image)
            new_hashes[idx] = h
            prev = self._hashes.get(idx)
            if prev is None or self._hamming(prev, h) > self._threshold:
                changed = True

        # 无论是否有变化都更新哈希，保证下一帧以最新画面为基准
        self._hashes = new_hashes
        return changed

    def reset(self) -> None:
        """清空历史哈希（窗口尺寸/区域配置变化后调用）."""
        self._hashes.clear()

    @staticmethod
    def _dhash(image: Image.Image, size: int = 9) -> int:
        """计算 8x8 差分哈希（64 位）.

        缩成 9x9 灰度图后比较相邻像素明暗，对亮度/轻微抖动不敏感，
        对文字内容变化敏感。
        """
        gray = image.convert("L").resize((size, size), Image.Resampling.BILINEAR)
        # tobytes() 返回 (size, size) 灰度像素序列，避免 getdata() 弃用警告
        pixels = list(gray.tobytes())
        h = 0
        for row in range(size - 1):
            offset = row * size
            for col in range(size - 1):
                left = pixels[offset + col]
                right = pixels[offset + col + 1]
                h = (h << 1) | (1 if left < right else 0)
        return h

    @staticmethod
    def _hamming(a: int, b: int) -> int:
        """两个 64 位哈希的汉明距离（不同位数）."""
        return (a ^ b).bit_count()


def _make_images(
    zones: List[Tuple[Image.Image, Tuple[int, int], float]],
) -> List[Image.Image]:
    """从 zones（image, offset, scale_ratio）中取出图像列表."""
    return [zone[0] for zone in zones]
