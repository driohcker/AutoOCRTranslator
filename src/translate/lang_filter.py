"""语言过滤工具.

用于判断一段文本是否属于预期的源语言，避免把 URL、UI 按钮、
纯数字等非目标语言内容送入翻译流程。
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# 常见语言特征字符范围
LANG_PATTERNS = {
    "ja": re.compile(r"[\u3040-\u309F\u30A0-\u30FF]"),  # 平假名 + 片假名
    "zh": re.compile(r"[\u4E00-\u9FFF]"),  # CJK 统一汉字
    "zh-CN": re.compile(r"[\u4E00-\u9FFF]"),
    "zh-TW": re.compile(r"[\u4E00-\u9FFF]"),
    "en": re.compile(r"^[a-zA-Z\s]+$"),
    "ko": re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]"),  # 韩文
}


def is_source_lang(text: str, source_lang: str) -> bool:
    """判断文本是否包含指定源语言的显著特征.

    对于日文，优先检查平假名/片假名（避免把中文汉字误判为日文）。
    对于中文，检查是否包含汉字。
    对于英文，检查是否包含字母。

    Args:
        text: 待判断文本。
        source_lang: 源语言代码，如 ja/zh/en/ko。

    Returns:
        文本是否明显属于源语言。
    """
    if not text or not text.strip():
        return False

    pattern = LANG_PATTERNS.get(source_lang.lower())
    if pattern is None:
        # 未定义的语言默认放行，避免误过滤
        return True

    return bool(pattern.search(text))


def should_translate(
    text: str,
    source_lang: str,
    min_length: int = 2,
    filter_url: bool = True,
    filter_number: bool = True,
    strict: bool = False,
) -> bool:
    """综合判断一段文本是否值得翻译.

    Args:
        text: 待判断文本。
        source_lang: 源语言代码。
        min_length: 最小有效长度，低于此长度跳过。
        filter_url: 是否过滤 URL。
        filter_number: 是否过滤纯数字。
        strict: 是否启用严格模式。严格模式下日文只翻译包含假名的文本，
                避免把中文 UI 汉字误判为日文。

    Returns:
        是否应当翻译该文本。
    """
    if not text:
        return False

    stripped = text.strip()
    if len(stripped) < min_length:
        return False

    # 过滤 URL
    if filter_url and ("http" in stripped or "www." in stripped or ".com" in stripped):
        return False

    # 过滤纯数字 / 纯符号
    if filter_number and re.fullmatch(r"[\d\s\W]+", stripped):
        return False

    source_lower = source_lang.lower()

    # 日文场景
    if source_lower in ("ja", "japan"):
        contains_kana = bool(LANG_PATTERNS["ja"].search(stripped))
        if contains_kana:
            return True

        # 明显英文 UI 过滤
        if LANG_PATTERNS["en"].fullmatch(stripped):
            return False

        # 严格模式：没有假名且非英文，可能是中文汉字，过滤掉
        if strict:
            logger.debug(f"严格模式过滤纯汉字文本: {stripped}")
            return False

        # 非严格模式：放行日文汉字
        return True

    return is_source_lang(stripped, source_lang)
