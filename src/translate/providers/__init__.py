"""翻译提供者实现集合."""

from src.translate.providers.aliyun import AliyunProvider
from src.translate.providers.deepl import DeepLProvider
from src.translate.providers.google_free import GoogleFreeProvider
from src.translate.providers.tencent import TencentProvider

__all__ = [
    "GoogleFreeProvider",
    "TencentProvider",
    "DeepLProvider",
    "AliyunProvider",
]
