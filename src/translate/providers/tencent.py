"""腾讯云机器翻译（TMT）提供者.

使用腾讯云官方机器翻译 API：
https://cloud.tencent.com/document/product/551/40566
需要 SecretId 和 SecretKey，支持免费额度。
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from src.translate.base import TranslationError, TranslationProvider

logger = logging.getLogger(__name__)


class TencentProvider(TranslationProvider):
    """腾讯云机器翻译 API 提供者."""

    HOST = "tmt.tencentcloudapi.com"
    SERVICE = "tmt"
    VERSION = "2018-03-21"
    ACTION = "TextTranslate"
    REGION = "ap-guangzhou"
    URL = f"https://{HOST}"

    LANG_MAP = {
        "ja": "ja",
        "japan": "ja",
        "zh": "zh",
        "zh-cn": "zh",
        "zh-tw": "zh-TW",
        "ch": "zh",
        "ch_tra": "zh-TW",
        "en": "en",
        "ko": "ko",
    }

    def __init__(
        self,
        secret_id: str = "",
        secret_key: str = "",
        region: str = "",
        timeout: int = 10,
        proxy: Optional[str] = None,
    ) -> None:
        """初始化.

        Args:
            secret_id: 腾讯云 SecretId。
            secret_key: 腾讯云 SecretKey。
            region: 地域，默认 ap-guangzhou。
            timeout: 请求超时时间（秒）。
            proxy: HTTP/HTTPS 代理地址，如 http://127.0.0.1:7890。
        """
        if not secret_id or not secret_key:
            raise TranslationError(
                "腾讯翻译需要提供 SecretId 和 SecretKey（对应设置中的 API Key 和 API Secret）"
            )
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region or self.REGION
        self.timeout = timeout
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """调用腾讯云机器翻译 API."""
        if not text or not text.strip():
            return ""

        payload: Dict[str, Any] = {
            "SourceText": text,
            "Source": self._normalize_lang(source_lang),
            "Target": self._normalize_lang(target_lang),
            "ProjectId": 0,
        }

        headers = self._build_headers(payload)

        try:
            response = requests.post(
                self.URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout,
                proxies=self.proxies,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise TranslationError(f"腾讯翻译网络请求失败: {e}") from e
        except Exception as e:
            raise TranslationError(f"解析腾讯翻译响应失败: {e}") from e

        if "Response" in data and "Error" in data["Response"]:
            error = data["Response"]["Error"]
            raise TranslationError(
                f"腾讯翻译接口错误 [{error.get('Code')}]: {error.get('Message')}"
            )

        try:
            return str(data["Response"]["TargetText"])
        except (KeyError, TypeError) as e:
            raise TranslationError(f"腾讯翻译响应格式异常: {e}") from e

    def _normalize_lang(self, lang: str) -> str:
        """标准化语言代码."""
        return self.LANG_MAP.get(lang.lower(), lang)

    def _build_headers(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """构建带 TC3-HMAC-SHA256 签名的请求头."""
        timestamp = int(time.time())
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        payload_json = json.dumps(payload)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        # 规范请求
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        canonical_headers = (
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.HOST}\n"
        )
        signed_headers = "content-type;host"
        canonical_request = (
            f"{http_request_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        # 待签名字符串
        credential_scope = f"{date}/{self.SERVICE}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()
        string_to_sign = (
            f"TC3-HMAC-SHA256\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashed_canonical_request}"
        )

        # 计算签名
        secret_date = hmac.new(
            f"TC3{self.secret_key}".encode("utf-8"),
            date.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_service = hmac.new(
            secret_date, self.SERVICE.encode("utf-8"), hashlib.sha256
        ).digest()
        secret_signing = hmac.new(
            secret_service, "tc3_request".encode("utf-8"), hashlib.sha256
        ).digest()
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"TC3-HMAC-SHA256 "
            f"Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.HOST,
            "X-TC-Action": self.ACTION,
            "X-TC-Version": self.VERSION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": self.region,
        }
