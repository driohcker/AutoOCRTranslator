"""Google Translate 免费网页接口提供者."""

import logging
import time
from typing import List, Optional

import requests

from src.translate.base import TranslationError, TranslationProvider

logger = logging.getLogger(__name__)


class GoogleFreeProvider(TranslationProvider):
    """Google Translate 免费网页接口提供者.

    注意：这是非官方接口，可能存在不稳定性或访问限制，
    仅作为默认免费方案降低上手门槛。如需稳定服务，请使用商业 API。
    """

    # 多个备用 endpoint，按顺序尝试
    ENDPOINTS = [
        "https://translate.googleapis.com/translate_a/single",
        "https://translate.google.com/translate_a/single",
    ]

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 2,
        proxy: Optional[str] = None,
    ):
        """初始化.

        Args:
            timeout: HTTP 请求超时时间（秒）. 默认 10。
            max_retries: 每个 endpoint 最大重试次数。默认 2。
            proxy: HTTP/HTTPS 代理地址，如 http://127.0.0.1:7890。
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """调用 Google Translate 免费接口翻译文本."""
        if not text or not text.strip():
            return ""

        params = {
            "client": "gtx",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text,
        }

        last_error: Optional[Exception] = None
        for url in self.ENDPOINTS:
            for attempt in range(self.max_retries + 1):
                try:
                    response = requests.get(
                        url,
                        params=params,
                        timeout=self.timeout,
                        proxies=self.proxies,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return self._parse_response(data)
                except requests.RequestException as e:
                    last_error = e
                    logger.warning(
                        f"翻译请求失败 ({url}, 尝试 {attempt + 1}/{self.max_retries + 1}): {e}"
                    )
                    if attempt < self.max_retries:
                        time.sleep(0.5 * (attempt + 1))
                except Exception as e:
                    raise TranslationError(f"解析翻译响应失败: {e}") from e

        # 所有 endpoint 都失败
        raise TranslationError(
            f"Google 翻译请求失败（已尝试 {len(self.ENDPOINTS)} 个接口，"
            f"共 {len(self.ENDPOINTS) * (self.max_retries + 1)} 次）: {last_error}. "
            f"建议：1) 配置 HTTP 代理；2) 切换其他翻译服务。"
        )

    def _parse_response(self, data) -> str:
        """解析 Google Translate 返回的 JSON 数据."""
        translated_parts: List[str] = []
        try:
            for sentence in data[0]:
                if sentence and len(sentence) > 0:
                    translated_parts.append(str(sentence[0]))
        except (IndexError, TypeError, KeyError) as e:
            raise TranslationError(f"翻译响应格式异常: {e}") from e

        return "".join(translated_parts)
