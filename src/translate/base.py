"""翻译提供者基类与异常."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """翻译相关异常."""

    pass


class TranslationProvider(ABC):
    """翻译提供者抽象基类."""

    @abstractmethod
    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        """翻译文本.

        Args:
            text: 待翻译文本.
            source_lang: 源语言代码，如 ja、en、zh-CN。
            target_lang: 目标语言代码，如 zh-CN、en。

        Returns:
            翻译后的文本.

        Raises:
            TranslationError: 翻译失败时抛出.
        """
        pass

    def test(self) -> bool:
        """测试翻译服务是否可用.

        默认实现尝试翻译一个简单的英文句子.
        """
        try:
            result = self.translate("hello", "en", "zh-CN")
            return bool(result)
        except Exception as e:
            logger.debug(f"翻译服务测试失败: {e}")
            return False
