"""RapidOCR 引擎封装.

RapidOCR 基于 ONNXRuntime，在 CPU 上通常比 PaddleOCR 更快，
适合需要较低延迟的实时字幕翻译场景。
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger(__name__)

OCRResult = Dict[str, Any]


class RapidOCREngine:
    """RapidOCR 引擎封装.

    提供与 PaddleOCREngine 相同的 recognize(image) 接口，便于互换。
    """

    LANG_MAP = {
        "japanese": "japan",
        "ja": "japan",
        "japan": "japan",
        "chinese": "ch",
        "zh": "ch",
        "zh_cn": "ch",
        "ch": "ch",
        "chinese_tra": "ch_tra",
        "zh_tw": "ch_tra",
        "ch_tra": "ch_tra",
        "english": "en",
        "en": "en",
    }

    def __init__(
        self,
        lang: str = "japan",
        drop_score: float = 0.7,
        min_height: int = 20,
        **kwargs,
    ) -> None:
        """初始化 RapidOCR 引擎.

        Args:
            lang: OCR 语言，目前 RapidOCR 主要支持 ch/en/japan 等。
            drop_score: 低于此置信度的结果会被过滤。
            min_height: 允许识别的最小文本高度（像素），游戏字幕通常较小。
            **kwargs: 传递给 RapidOCR 构造函数的参数。
        """
        self.lang = self._normalize_lang(lang)
        self.drop_score = drop_score

        logger.info(
            f"初始化 RapidOCR: lang={self.lang}, drop_score={drop_score}, "
            f"min_height={min_height}"
        )

        # RapidOCR 构造函数支持的参数有限，透传已知常用参数
        self._ocr = RapidOCR(
            text_score=drop_score,
            min_height=min_height,
            **kwargs,
        )

    def _normalize_lang(self, lang: str) -> str:
        """标准化语言名称."""
        return self.LANG_MAP.get(lang.lower(), lang.lower())

    def recognize(self, image: Optional[Image.Image]) -> List[OCRResult]:
        """识别图像中的文字.

        Args:
            image: PIL.Image 对象。

        Returns:
            OCR 结果列表，每项包含 text、box、score。
        """
        if image is None:
            return []

        try:
            np_image = np.array(image)
            results, _ = self._ocr(np_image)
        except Exception as e:
            logger.error(f"RapidOCR 识别失败: {e}")
            return []

        if not results:
            return []

        return self._parse_result(results)

    def _parse_result(self, raw: List[Any]) -> List[OCRResult]:
        """解析 RapidOCR 输出为统一格式."""
        parsed: List[OCRResult] = []
        for item in raw:
            if len(item) < 3:
                continue
            box, text, score_str = item[0], item[1], item[2]
            try:
                score = float(score_str)
            except (TypeError, ValueError):
                score = 0.0

            if score < self.drop_score:
                continue

            # box 已经是 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)] 格式
            if len(box) >= 4:
                box = [(int(p[0]), int(p[1])) for p in box[:4]]
            else:
                box = []

            parsed.append(
                {
                    "text": str(text),
                    "box": box,
                    "score": score,
                }
            )

        return parsed
