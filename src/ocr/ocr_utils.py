"""OCR 引擎创建辅助函数.

用于在主进程和翻译子进程中统一构造 OCR 引擎，避免重复代码.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def create_ocr_engine(
    engine: str,
    lang: str,
    params: Dict[str, Any],
    use_gpu: bool = False,
) -> Any:
    """根据配置创建 OCR 引擎.

    Args:
        engine: "rapid" 或 "paddle"。
        lang: OCR 语言代码，如 "japan" / "ch" / "en"。
        params: 包含 drop_score、det_db_thresh、det_db_box_thresh、
            det_limit_side_len、min_height 等字段的字典。
        use_gpu: 是否尝试使用 GPU（仅 paddle 有效）。

    Returns:
        OCR 引擎实例。
    """
    if engine == "rapid":
        from src.ocr.rapid_ocr import RapidOCREngine

        logger.info(
            f"创建 RapidOCR 引擎: lang={lang}, "
            f"drop_score={params.get('drop_score', 0.7)}, "
            f"min_height={params.get('min_height', 20)}"
        )
        return RapidOCREngine(
            lang=lang,
            drop_score=params.get("drop_score", 0.7),
            min_height=params.get("min_height", 20),
        )

    from src.ocr.paddle_ocr import PaddleOCREngine

    if use_gpu:
        try:
            import paddle

            if not paddle.is_compiled_with_cuda():
                logger.warning(
                    "配置使用 GPU，但当前 Paddle 未编译 CUDA，将回退到 CPU"
                )
                use_gpu = False
        except Exception as e:
            logger.warning(f"GPU 检测失败: {e}，将回退到 CPU")
            use_gpu = False

    logger.info(
        f"创建 PaddleOCR 引擎: lang={lang}, use_gpu={use_gpu}, "
        f"drop_score={params.get('drop_score', 0.7)}, "
        f"det_db_thresh={params.get('det_db_thresh', 0.5)}, "
        f"det_db_box_thresh={params.get('det_db_box_thresh', 0.5)}"
    )
    return PaddleOCREngine(
        lang=lang,
        use_gpu=use_gpu,
        drop_score=params.get("drop_score", 0.7),
        det_db_thresh=params.get("det_db_thresh", 0.5),
        det_db_box_thresh=params.get("det_db_box_thresh", 0.5),
        text_det_limit_side_len=params.get("det_limit_side_len", 480),
    )
