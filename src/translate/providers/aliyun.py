"""阿里云机器翻译提供者.

使用阿里云通用机器翻译 API：
https://help.aliyun.com/document_detail/158244.html
需要 AccessKey ID 和 AccessKey Secret。
"""

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

from src.translate.base import TranslationError, TranslationProvider

logger = logging.getLogger(__name__)


class AliyunProvider(TranslationProvider):
    """阿里云机器翻译 API 提供者."""

    ENDPOINT = "https://mt.aliyuncs.com/"
    LANG_MAP = {
        "ja": "ja",
        "japan": "ja",
        "zh": "zh",
        "zh-cn": "zh",
        "zh-tw": "zh-tw",
        "ch": "zh",
        "ch_tra": "zh-tw",
        "en": "en",
        "ko": "ko",
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
            api_key: AccessKey ID。
            api_secret: AccessKey Secret。
            timeout: 请求超时时间（秒）。
            proxy: HTTP/HTTPS 代理地址。
        """
        if not api_key or not api_secret:
            raise TranslationError(
                "阿里云翻译需要提供 AccessKey ID 和 AccessKey Secret"
            )
        self.access_key_id = api_key
        self.access_key_secret = api_secret
        self.timeout = timeout
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """调用阿里云机器翻译 API."""
        if not text or not text.strip():
            return ""

        params: Dict[str, Any] = {
            "Format": "JSON",
            "Version": "2018-10-12",
            "AccessKeyId": self.access_key_id,
            "SignatureMethod": "HMAC-SHA1",
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SignatureVersion": "1.0",
            "SignatureNonce": str(int(time.time() * 1000)),
            "Action": "TranslateGeneral",
            "FormatType": "text",
            "SourceLanguage": self._normalize_lang(source_lang),
            "TargetLanguage": self._normalize_lang(target_lang),
            "SourceText": text,
            "Scene": "general",
        }

        params["Signature"] = self._sign(params)

        try:
            response = requests.get(
                self.ENDPOINT,
                params=params,
                timeout=self.timeout,
                proxies=self.proxies,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise TranslationError(f"阿里云翻译网络请求失败: {e}") from e
        except Exception as e:
            raise TranslationError(f"解析阿里云翻译响应失败: {e}") from e

        if data.get("Code") and str(data.get("Code")) != "200":
            raise TranslationError(
                f"阿里云翻译接口错误 [{data.get('Code')}]: {data.get('Message', '')}"
            )

        try:
            return str(data["Data"]["Translated"])
        except (KeyError, TypeError) as e:
            raise TranslationError(f"阿里云翻译响应格式异常: {e}") from e

    def _normalize_lang(self, lang: str) -> str:
        """标准化语言代码."""
        return self.LANG_MAP.get(lang.lower(), lang)

    def _sign(self, params: Dict[str, Any]) -> str:
        """计算阿里云 HMAC-SHA1 签名."""
        sorted_params = sorted(params.items())
        canonical_query = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(str(v))}"
            for k, v in sorted_params
        )
        string_to_sign = f"GET&%2F&{self._percent_encode(canonical_query)}"
        key = f"{self.access_key_secret}&".encode("utf-8")
        signature = hmac.new(
            key, string_to_sign.encode("utf-8"), hashlib.sha1
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def _percent_encode(value: str) -> str:
        """阿里云要求的 URL 编码（空格编码为 %20，* 不编码）."""
        encoded = urllib.parse.quote(value, safe="")
        encoded = encoded.replace("+", "%2B")
        encoded = encoded.replace("*", "%2A")
        encoded = encoded.replace("%7E", "~")
        return encoded
