"""ROI 预处理工具.

把截图按配置裁剪、缩放到适合 OCR 的尺寸，供 capture 线程和翻译 worker 复用.
"""

from typing import List, Optional, Tuple

from PIL import Image


# OCR 区域预设：key -> [x_ratio, y_ratio, w_ratio, h_ratio]
ROI_PRESETS = {
    "subtitle": [0.1, 0.75, 0.8, 0.2],  # 底部居中字幕区
    "bottom": [0.0, 0.7, 1.0, 0.3],     # 底部全宽
    "full": [0.0, 0.0, 1.0, 1.0],       # 全屏
}

# 不同 ROI 预设对应的 OCR 参数：面积越大，分辨率/阈值越宽松
ROI_OCR_PARAMS = {
    "subtitle": {
        "max_width": 480,
        "det_limit_side_len": 480,
        "drop_score": 0.6,
        "det_db_thresh": 0.5,
        "det_db_box_thresh": 0.5,
        "min_height": 20,
    },
    "bottom": {
        "max_width": 640,
        "det_limit_side_len": 640,
        "drop_score": 0.5,
        "det_db_thresh": 0.4,
        "det_db_box_thresh": 0.4,
        "min_height": 20,
    },
    "full": {
        "max_width": 1280,
        "det_limit_side_len": 1280,
        "drop_score": 0.45,
        "det_db_thresh": 0.3,
        "det_db_box_thresh": 0.3,
        "min_height": 15,
    },
    "custom_zones": {
        "max_width": 1280,
        "det_limit_side_len": 1280,
        "drop_score": 0.45,
        "det_db_thresh": 0.3,
        "det_db_box_thresh": 0.3,
        "min_height": 15,
    },
}


def get_roi_from_preset(
    preset: str, custom_roi: Optional[list] = None
) -> List[float]:
    """根据预设名称获取 ROI.

    Args:
        preset: 预设名称 subtitle / bottom / full / custom / custom_zones。
        custom_roi: 自定义 ROI，仅在 preset 为 custom 时使用。

    Returns:
        ROI 列表 [x, y, w, h]（相对坐标 0~1）。
    """
    if preset == "custom" and custom_roi and len(custom_roi) == 4:
        return list(custom_roi)
    return ROI_PRESETS.get(preset, ROI_PRESETS["subtitle"])


def crop_roi(
    image: Image.Image, roi_ratios: List[float]
) -> Tuple[Image.Image, Tuple[int, int]]:
    """按相对坐标裁剪 ROI.

    Args:
        image: 原始图像。
        roi_ratios: [x_ratio, y_ratio, w_ratio, h_ratio]。

    Returns:
        (裁剪后的图像, 在原始图像中的偏移量 (x, y))。
    """
    if not roi_ratios or len(roi_ratios) != 4:
        return image.copy(), (0, 0)

    x_ratio, y_ratio, w_ratio, h_ratio = roi_ratios
    left = int(image.width * x_ratio)
    top = int(image.height * y_ratio)
    right = min(int(left + image.width * w_ratio), image.width)
    bottom = min(int(top + image.height * h_ratio), image.height)

    if right <= left or bottom <= top:
        return image.copy(), (0, 0)

    return image.crop((left, top, right, bottom)), (left, top)


def resize_for_ocr(
    image: Image.Image, max_width: int
) -> Tuple[Image.Image, float]:
    """如果图片宽度超过限制，等比缩放以加速 OCR.

    Returns:
        (缩放后的图像, scale_ratio)。scale_ratio 用于把识别框坐标映射回原始尺寸。
    """
    if image.width <= max_width:
        return image, 1.0

    scale_ratio = max_width / image.width
    new_size = (max_width, int(image.height * scale_ratio))
    return image.resize(new_size, Image.Resampling.LANCZOS), scale_ratio


def prepare_single_zone(
    image: Image.Image,
    preset: str,
    custom_roi: Optional[List[float]] = None,
    max_width: Optional[int] = None,
) -> Tuple[Image.Image, Tuple[int, int], float]:
    """准备单区域 OCR 输入.

    Args:
        image: 原始截图。
        preset: ROI 预设名称。
        custom_roi: 自定义 ROI（preset 为 custom 时使用）。
        max_width: 最大 OCR 宽度；None 时使用预设配置。

    Returns:
        (缩放后的图像, 偏移量, 缩放比例)。
    """
    roi = get_roi_from_preset(preset, custom_roi)
    cropped, offset = crop_roi(image, roi)

    if max_width is None:
        max_width = ROI_OCR_PARAMS.get(preset, ROI_OCR_PARAMS["subtitle"])[
            "max_width"
        ]

    resized, scale_ratio = resize_for_ocr(cropped, max_width)
    return resized, offset, scale_ratio


def prepare_multi_zones(
    image: Image.Image,
    zones: List[List[float]],
    max_width: int,
) -> List[Tuple[Image.Image, Tuple[int, int], float]]:
    """准备多区域 OCR 输入.

    Args:
        image: 原始截图。
        zones: 每个元素为 [x_ratio, y_ratio, w_ratio, h_ratio]。
        max_width: 每个子区域最大 OCR 宽度。

    Returns:
        每个有效区域对应的 (图像, 偏移量, 缩放比例) 列表。
    """
    prepared: List[Tuple[Image.Image, Tuple[int, int], float]] = []
    for zone in zones:
        if len(zone) != 4:
            continue
        cropped, offset = crop_roi(image, zone)
        if cropped.width <= 0 or cropped.height <= 0:
            continue
        resized, scale_ratio = resize_for_ocr(cropped, max_width)
        prepared.append((resized, offset, scale_ratio))
    return prepared
