"""翻译模块.

提供翻译器工厂，支持多种翻译提供者。
"""

import logging
from typing import Any, Dict, Type

from src.translate.base import TranslationError, TranslationProvider

logger = logging.getLogger(__name__)


class Translator:
    """翻译器，根据配置创建并调用对应的翻译提供者."""

    _providers: Dict[str, Type[TranslationProvider]] = {}

    def __init__(self, provider_name: str = "google_free", **kwargs):
        """初始化翻译器.

        Args:
            provider_name: 提供者名称，如 google_free / tencent / deep_l。
            **kwargs: 传递给提供者的初始化参数。

        Raises:
            ValueError: 提供者名称未知时抛出。
        """
        # 延迟注册，避免循环导入
        self._register_default_providers()

        provider_cls = self._providers.get(provider_name)
        if provider_cls is None:
            raise ValueError(f"未知的翻译提供者: {provider_name}")
        self.provider = provider_cls(**kwargs)
        logger.info(f"已创建翻译器，使用提供者: {provider_name}")

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """翻译文本."""
        return self.provider.translate(text, source_lang, target_lang)

    def test(self) -> bool:
        """测试翻译服务是否可用."""
        return self.provider.test()

    @classmethod
    def register_provider(
        cls, name: str, provider_cls: Type[TranslationProvider]
    ) -> None:
        """注册新的翻译提供者.

        Args:
            name: 提供者名称。
            provider_cls: 翻译提供者类，必须继承 TranslationProvider。
        """
        if not issubclass(provider_cls, TranslationProvider):
            raise TypeError("provider_cls 必须继承 TranslationProvider")
        cls._providers[name] = provider_cls

    @classmethod
    def list_providers(cls) -> list:
        """列出所有已注册的提供者名称."""
        cls._register_default_providers()
        return list(cls._providers.keys())

    @classmethod
    def _register_default_providers(cls) -> None:
        """注册内置默认翻译提供者（延迟导入避免循环依赖）."""
        if cls._providers:
            return

        from src.translate.providers.deepl import DeepLProvider
        from src.translate.providers.google_free import GoogleFreeProvider
        from src.translate.providers.tencent import TencentProvider

        cls.register_provider("google_free", GoogleFreeProvider)
        cls.register_provider("tencent", TencentProvider)
        cls.register_provider("deep_l", DeepLProvider)
        cls.register_provider("aliyun", AliyunProvider)


# 向后兼容：外部仍可从本模块导入这些类和异常
from src.translate.providers.aliyun import AliyunProvider
from src.translate.providers.deepl import DeepLProvider
from src.translate.providers.google_free import GoogleFreeProvider
from src.translate.providers.tencent import TencentProvider


def create_translator(translate_config: Dict[str, Any]) -> "Translator":
    """根据配置字典创建翻译器.

    Args:
        translate_config: 包含 provider、proxy、api_key、api_secret 等字段。

    Returns:
        Translator 实例。
    """
    provider = translate_config.get("provider", "google_free")
    proxy = translate_config.get("proxy", "") or None
    api_key = translate_config.get("api_key", "")
    api_secret = translate_config.get("api_secret", "")

    provider_kwargs: Dict[str, Any] = {
        "proxy": proxy,
        # 超时由配置控制（settings.yaml translate.timeout）
        "timeout": int(translate_config.get("timeout", 5)),
    }
    if provider == "google_free":
        # 仅 google_free 支持重试次数配置
        provider_kwargs["max_retries"] = int(
            translate_config.get("max_retries", 1)
        )
    if provider == "tencent":
        provider_kwargs["secret_id"] = api_key
        provider_kwargs["secret_key"] = api_secret
    elif provider in ("deep_l", "aliyun"):
        provider_kwargs["api_key"] = api_key
        provider_kwargs["api_secret"] = api_secret

    return Translator(provider_name=provider, **provider_kwargs)

__all__ = [
    "Translator",
    "TranslationError",
    "TranslationProvider",
    "GoogleFreeProvider",
    "TencentProvider",
    "DeepLProvider",
    "AliyunProvider",
]
