"""OCR 模块，基于 PaddleOCR.

注意：在 Python 3.13 + PaddlePaddle 3.x 环境下，必须禁用 oneDNN 才能避免
`ConvertPirAttribute2RuntimeAttribute` 错误。本模块在导入 paddleocr 前通过
环境变量 `FLAGS_use_mkldnn=0` 处理此问题。
"""

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

# 必须在导入 paddleocr 之前设置，禁用 oneDNN 以兼容 Python 3.13
os.environ.setdefault("FLAGS_use_mkldnn", "0")

from paddleocr import PaddleOCR  # noqa: E402

logger = logging.getLogger(__name__)


OCRResult = Dict[str, Any]
"""OCR 识别结果项.

格式: {
    "text": str,           # 识别文本
    "box": List[Tuple[int, int]],  # 四边形边界框坐标
    "score": float,        # 置信度
}
"""


class PaddleOCREngine:
    """PaddleOCR 引擎封装.

    支持日文(japan)、简体中文(ch)、繁体中文(ch_tra)、英文(en)等语言.
    """

    # 语言名称标准化映射
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
        use_gpu: bool = False,
        drop_score: float = 0.7,
        det_db_thresh: float = 0.5,
        det_db_box_thresh: float = 0.5,
        **kwargs,
    ):
        """初始化 PaddleOCR 引擎.

        Args:
            lang: OCR 语言，如 japan/ch/ch_tra/en。
            use_gpu: 是否使用 GPU。默认 False（CPU）。
            drop_score: 低于此置信度的结果会被过滤。默认 0.7。
            det_db_thresh: 文本检测阈值。默认 0.5。
            det_db_box_thresh: 文本检测框阈值。默认 0.5。
            **kwargs: 其他传递给 PaddleOCR 的参数。
        """
        self.lang = self._normalize_lang(lang)
        self.drop_score = drop_score
        self.device = "gpu:0" if use_gpu else "cpu"

        logger.info(
            f"初始化 PaddleOCR: lang={self.lang}, device={self.device}, "
            f"drop_score={drop_score}, det_db_thresh={det_db_thresh}, "
            f"det_db_box_thresh={det_db_box_thresh}"
        )

        # 游戏字幕场景通常不需要文档方向判断和去扭曲，关闭以加速初始化
        disable_preprocessor = kwargs.pop("use_doc_orientation_classify", False)
        disable_unwarping = kwargs.pop("use_doc_unwarping", False)
        disable_textline_orient = kwargs.pop("use_textline_orientation", False)
        # min_height 是 RapidOCR 专属参数，PaddleOCR 不支持，弹出忽略
        kwargs.pop("min_height", None)

        self._ocr = PaddleOCR(
            lang=self.lang,
            device=self.device,
            enable_mkldnn=False,  # Python 3.13 兼容性要求
            use_doc_orientation_classify=disable_preprocessor,
            use_doc_unwarping=disable_unwarping,
            use_textline_orientation=disable_textline_orient,
            text_det_thresh=det_db_thresh,
            text_det_box_thresh=det_db_box_thresh,
            text_rec_score_thresh=drop_score,
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
            results = self._ocr.predict(np_image)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return []

        if not results:
            return []

        return self._parse_result(results[0])

    def _parse_result(self, raw: Dict[str, Any]) -> List[OCRResult]:
        """解析 PaddleOCR 输出为统一格式."""
        texts = raw.get("rec_texts", [])
        scores = raw.get("rec_scores", [])
        boxes = raw.get("rec_boxes", [])
        polys = raw.get("rec_polys", []) or raw.get("dt_polys", [])

        parsed: List[OCRResult] = []
        for i in range(len(texts)):
            score = float(scores[i]) if i < len(scores) else 0.0
            if score < self.drop_score:
                continue

            # 优先使用四边形坐标，否则用矩形框推导
            if i < len(polys) and len(polys[i]) >= 4:
                box = [(int(p[0]), int(p[1])) for p in polys[i]]
            elif i < len(boxes):
                x1, y1, x2, y2 = [int(v) for v in boxes[i]]
                box = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            else:
                box = []

            parsed.append(
                {
                    "text": str(texts[i]),
                    "box": box,
                    "score": score,
                }
            )

        return parsed
