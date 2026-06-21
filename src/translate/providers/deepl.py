"""DeepL 翻译 API 提供者.

支持 DeepL Free 和 Pro API。
"""

import logging
from typing import Any, Dict, Optional

import requests

from src.translate.base import TranslationError, TranslationProvider

logger = logging.getLogger(__name__)


class DeepLProvider(TranslationProvider):
    """DeepL API 提供者."""

    LANG_MAP = {
        "ja": "JA",
        "japan": "JA",
        "zh": "ZH",
        "zh-cn": "ZH",
        "zh-tw": "ZH",
        "ch": "ZH",
        "ch_tra": "ZH",
        "en": "EN",
        "ko": "KO",
    }

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        timeout: int = 10,
        proxy: Optional[str] = None,
    ) -> None:
        """初始化.

        Args:
            api_key: DeepL Auth Key。free 版以 :fx 结尾。
            api_secret: 兼容参数，DeepL 只需要 api_key。
            timeout: 请求超时时间（秒）。
            proxy: HTTP/HTTPS 代理地址。
        """
        key = api_key or api_secret
        if not key:
            raise TranslationError("DeepL 翻译需要提供 API Key")

        self.api_key = key
        self.timeout = timeout
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

        # 以 :fx 结尾的是免费版 API
        if self.api_key.endswith(":fx"):
            self.base_url = "https://api-free.deepl.com/v2/translate"
        else:
            self.base_url = "https://api.deepl.com/v2/translate"

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """调用 DeepL API 翻译文本."""
        if not text or not text.strip():
            return ""

        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        data: Dict[str, Any] = {
            "text": [text],
            "target_lang": self._normalize_lang(target_lang),
        }
        source = self._normalize_lang(source_lang)
        if source:
            data["source_lang"] = source

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=self.timeout,
                proxies=self.proxies,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as e:
            raise TranslationError(f"DeepL 网络请求失败: {e}") from e
        except Exception as e:
            raise TranslationError(f"解析 DeepL 响应失败: {e}") from e

        try:
            translations = result.get("translations", [])
            if not translations:
                raise TranslationError("DeepL 返回空翻译结果")
            return str(translations[0]["text"])
        except (KeyError, TypeError, IndexError) as e:
            raise TranslationError(f"DeepL 响应格式异常: {e}") from e

    def _normalize_lang(self, lang: str) -> str:
        """标准化语言代码为 DeepL 格式."""
        return self.LANG_MAP.get(lang.lower(), lang.upper())
