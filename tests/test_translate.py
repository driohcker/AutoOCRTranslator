"""翻译模块测试."""

import json
import unittest
from unittest.mock import MagicMock, patch

from src.translate.translator import (
    AliyunProvider,
    DeepLProvider,
    GoogleFreeProvider,
    TencentProvider,
    TranslationError,
    TranslationProvider,
    Translator,
    create_translator,
)


class MockProvider(TranslationProvider):
    """测试用翻译提供者."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> str:
        return f"{self.prefix}{text}"


class TestGoogleFreeProvider(unittest.TestCase):
    """GoogleFreeProvider 测试."""

    @patch("src.translate.providers.google_free.requests.get")
    def test_translate_normal(self, mock_get: MagicMock) -> None:
        """测试正常翻译流程."""
        mock_get.return_value.json.return_value = [
            [["你好", "こんにちは", None, None, 1]],
            "ja",
            None,
            1,
            None,
            None,
            1.0,
            [],
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        provider = GoogleFreeProvider()
        result = provider.translate("こんにちは", "ja", "zh-CN")
        self.assertEqual(result, "你好")

        # 验证请求参数
        call_args = mock_get.call_args
        self.assertEqual(call_args.kwargs["params"]["sl"], "ja")
        self.assertEqual(call_args.kwargs["params"]["tl"], "zh-CN")
        self.assertEqual(call_args.kwargs["params"]["q"], "こんにちは")

    @patch("src.translate.providers.google_free.requests.get")
    def test_translate_multiple_sentences(self, mock_get: MagicMock) -> None:
        """测试多句合并."""
        mock_get.return_value.json.return_value = [
            [
                ["你好", "こんにちは", None, None, 1],
                ["世界", "せかい", None, None, 1],
            ]
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        provider = GoogleFreeProvider()
        result = provider.translate("こんにちはせかい", "ja", "zh-CN")
        self.assertEqual(result, "你好世界")

    def test_translate_empty_text(self) -> None:
        """测试空文本返回空字符串."""
        provider = GoogleFreeProvider()
        self.assertEqual(provider.translate("", "ja", "zh-CN"), "")
        self.assertEqual(provider.translate("   ", "ja", "zh-CN"), "")

    @patch("src.translate.providers.google_free.requests.get")
    def test_translate_network_error(self, mock_get: MagicMock) -> None:
        """测试网络失败抛出 TranslationError."""
        from requests import RequestException

        mock_get.side_effect = RequestException("connection timeout")

        provider = GoogleFreeProvider()
        with self.assertRaises(TranslationError):
            provider.translate("こんにちは", "ja", "zh-CN")

    @patch("src.translate.providers.google_free.requests.get")
    def test_translate_malformed_response(self, mock_get: MagicMock) -> None:
        """测试异常响应格式抛出 TranslationError."""
        mock_get.return_value.json.return_value = {"error": "invalid"}
        mock_get.return_value.raise_for_status = MagicMock()

        provider = GoogleFreeProvider()
        with self.assertRaises(TranslationError):
            provider.translate("こんにちは", "ja", "zh-CN")


class TestDeepLProvider(unittest.TestCase):
    """DeepLProvider 测试."""

    @patch("src.translate.providers.deepl.requests.post")
    def test_translate_normal(self, mock_post: MagicMock) -> None:
        """测试正常翻译流程，验证 JSON 请求体格式."""
        mock_post.return_value.json.return_value = {
            "translations": [
                {"detected_source_language": "JA", "text": "你好"}
            ]
        }
        mock_post.return_value.raise_for_status = MagicMock()

        provider = DeepLProvider(api_key="test-key:fx")
        result = provider.translate("こんにちは", "ja", "zh-CN")
        self.assertEqual(result, "你好")

        call_args = mock_post.call_args
        self.assertEqual(call_args.kwargs["headers"]["Authorization"], "DeepL-Auth-Key test-key:fx")
        self.assertEqual(call_args.kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(call_args.kwargs["json"]["text"], ["こんにちは"])
        self.assertEqual(call_args.kwargs["json"]["source_lang"], "JA")
        self.assertEqual(call_args.kwargs["json"]["target_lang"], "ZH")
        self.assertEqual(call_args.args[0], "https://api-free.deepl.com/v2/translate")

    @patch("src.translate.providers.deepl.requests.post")
    def test_translate_pro_endpoint(self, mock_post: MagicMock) -> None:
        """测试 Pro API endpoint."""
        mock_post.return_value.json.return_value = {
            "translations": [{"detected_source_language": "JA", "text": "你好"}]
        }
        mock_post.return_value.raise_for_status = MagicMock()

        provider = DeepLProvider(api_key="test-key")
        provider.translate("こんにちは", "ja", "zh-CN")

        call_args = mock_post.call_args
        self.assertEqual(call_args.args[0], "https://api.deepl.com/v2/translate")

    def test_translate_empty_text(self) -> None:
        """测试空文本返回空字符串."""
        provider = DeepLProvider(api_key="test-key:fx")
        self.assertEqual(provider.translate("", "ja", "zh-CN"), "")
        self.assertEqual(provider.translate("   ", "ja", "zh-CN"), "")

    def test_missing_api_key(self) -> None:
        """测试缺少 API Key 时抛出异常."""
        with self.assertRaises(TranslationError):
            DeepLProvider(api_key="", api_secret="")

    @patch("src.translate.providers.deepl.requests.post")
    def test_translate_network_error(self, mock_post: MagicMock) -> None:
        """测试网络失败抛出 TranslationError."""
        from requests import RequestException

        mock_post.side_effect = RequestException("connection timeout")

        provider = DeepLProvider(api_key="test-key:fx")
        with self.assertRaises(TranslationError):
            provider.translate("こんにちは", "ja", "zh-CN")

    @patch("src.translate.providers.deepl.requests.post")
    def test_translate_api_error(self, mock_post: MagicMock) -> None:
        """测试 DeepL 返回错误响应."""
        mock_post.return_value.json.return_value = {"message": "Wrong endpoint"}
        mock_post.return_value.raise_for_status = MagicMock()

        provider = DeepLProvider(api_key="test-key:fx")
        with self.assertRaises(TranslationError):
            provider.translate("こんにちは", "ja", "zh-CN")


class TestAliyunProvider(unittest.TestCase):
    """AliyunProvider 测试."""

    @patch("src.translate.providers.aliyun.requests.get")
    def test_translate_normal(self, mock_get: MagicMock) -> None:
        """测试正常翻译流程，Code=200 不应当成错误."""
        mock_get.return_value.json.return_value = {
            "Code": 200,
            "Message": "success",
            "RequestId": "req-123",
            "Data": {"Translated": "你好", "WordCount": 2},
        }
        mock_get.return_value.raise_for_status = MagicMock()

        provider = AliyunProvider(api_key="access-id", api_secret="access-secret")
        result = provider.translate("hello", "en", "zh-CN")
        self.assertEqual(result, "你好")

        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        self.assertEqual(params["Action"], "TranslateGeneral")
        self.assertEqual(params["SourceLanguage"], "en")
        self.assertEqual(params["TargetLanguage"], "zh")
        self.assertEqual(params["SourceText"], "hello")
        self.assertEqual(params["FormatType"], "text")
        self.assertEqual(params["Scene"], "general")
        self.assertIn("Signature", params)

    @patch("src.translate.providers.aliyun.requests.get")
    def test_translate_api_error(self, mock_get: MagicMock) -> None:
        """测试阿里云接口返回非 200 Code 时抛出异常."""
        mock_get.return_value.json.return_value = {
            "Code": "10001",
            "Message": "timeout",
            "RequestId": "req-123",
        }
        mock_get.return_value.raise_for_status = MagicMock()

        provider = AliyunProvider(api_key="access-id", api_secret="access-secret")
        with self.assertRaises(TranslationError) as ctx:
            provider.translate("hello", "en", "zh-CN")
        self.assertIn("10001", str(ctx.exception))

    def test_translate_empty_text(self) -> None:
        """测试空文本返回空字符串."""
        provider = AliyunProvider(api_key="access-id", api_secret="access-secret")
        self.assertEqual(provider.translate("", "en", "zh-CN"), "")

    def test_missing_credentials(self) -> None:
        """测试缺少密钥时抛出异常."""
        with self.assertRaises(TranslationError):
            AliyunProvider(api_key="", api_secret="")

    @patch("src.translate.providers.aliyun.requests.get")
    def test_translate_network_error(self, mock_get: MagicMock) -> None:
        """测试网络失败抛出 TranslationError."""
        from requests import RequestException

        mock_get.side_effect = RequestException("connection timeout")

        provider = AliyunProvider(api_key="access-id", api_secret="access-secret")
        with self.assertRaises(TranslationError):
            provider.translate("hello", "en", "zh-CN")


class TestTencentProvider(unittest.TestCase):
    """TencentProvider 测试."""

    @patch("src.translate.providers.tencent.requests.post")
    @patch("src.translate.providers.tencent.time.time", return_value=1609459200.0)
    def test_translate_normal(self, mock_time: MagicMock, mock_post: MagicMock) -> None:
        """测试正常翻译流程并验证 TC3 签名规范."""
        mock_post.return_value.json.return_value = {
            "Response": {
                "TargetText": "你好",
                "Source": "en",
                "Target": "zh",
                "RequestId": "req-123",
            }
        }
        mock_post.return_value.raise_for_status = MagicMock()

        provider = TencentProvider(secret_id="secret-id", secret_key="secret-key")
        result = provider.translate("hello", "en", "zh-CN")
        self.assertEqual(result, "你好")

        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Host"], "tmt.tencentcloudapi.com")
        self.assertEqual(headers["X-TC-Action"], "TextTranslate")
        self.assertEqual(headers["X-TC-Version"], "2018-03-21")
        self.assertEqual(headers["X-TC-Timestamp"], "1609459200")
        self.assertEqual(headers["X-TC-Region"], "ap-guangzhou")

        auth = headers["Authorization"]
        self.assertTrue(auth.startswith("TC3-HMAC-SHA256"))
        self.assertIn("SignedHeaders=content-type;host", auth)

        body = json.loads(call_args.kwargs["data"])
        self.assertEqual(body["SourceText"], "hello")
        self.assertEqual(body["Source"], "en")
        self.assertEqual(body["Target"], "zh")
        self.assertEqual(body["ProjectId"], 0)

    @patch("src.translate.providers.tencent.requests.post")
    @patch("src.translate.providers.tencent.time.time", return_value=1609459200.0)
    def test_signature_against_manual(self, mock_time: MagicMock, mock_post: MagicMock) -> None:
        """验证 TC3-HMAC-SHA256 签名与手动计算结果一致."""
        mock_post.return_value.json.return_value = {
            "Response": {"TargetText": "你好", "RequestId": "req-123"}
        }
        mock_post.return_value.raise_for_status = MagicMock()

        secret_id = "AKIDz8krbsJ5yKBZQpn74WFkmLPx3*******"
        secret_key = "Gu5t9xGARNpq86cd98joQYCN3*******"
        provider = TencentProvider(secret_id=secret_id, secret_key=secret_key)
        provider.translate("hello", "en", "zh-CN")

        headers = mock_post.call_args.kwargs["headers"]
        expected_auth = (
            "TC3-HMAC-SHA256 Credential=AKIDz8krbsJ5yKBZQpn74WFkmLPx3*******/"
            "2021-01-01/tmt/tc3_request, SignedHeaders=content-type;host, "
            "Signature=6219423fdd3e0c47619ef27de05483edbdd2233bcb45d1f3447bcba75ea85d8b"
        )
        self.assertEqual(headers["Authorization"], expected_auth)

    @patch("src.translate.providers.tencent.requests.post")
    def test_translate_api_error(self, mock_post: MagicMock) -> None:
        """测试腾讯云接口返回错误."""
        mock_post.return_value.json.return_value = {
            "Response": {
                "Error": {"Code": "AuthFailure.SignatureFailure", "Message": "签名错误"},
                "RequestId": "req-123",
            }
        }
        mock_post.return_value.raise_for_status = MagicMock()

        provider = TencentProvider(secret_id="secret-id", secret_key="secret-key")
        with self.assertRaises(TranslationError) as ctx:
            provider.translate("hello", "en", "zh-CN")
        self.assertIn("AuthFailure.SignatureFailure", str(ctx.exception))

    def test_translate_empty_text(self) -> None:
        """测试空文本返回空字符串."""
        provider = TencentProvider(secret_id="secret-id", secret_key="secret-key")
        self.assertEqual(provider.translate("", "en", "zh-CN"), "")

    def test_missing_credentials(self) -> None:
        """测试缺少密钥时抛出异常."""
        with self.assertRaises(TranslationError):
            TencentProvider(secret_id="", secret_key="")

    @patch("src.translate.providers.tencent.requests.post")
    def test_translate_network_error(self, mock_post: MagicMock) -> None:
        """测试网络失败抛出 TranslationError."""
        from requests import RequestException

        mock_post.side_effect = RequestException("connection timeout")

        provider = TencentProvider(secret_id="secret-id", secret_key="secret-key")
        with self.assertRaises(TranslationError):
            provider.translate("hello", "en", "zh-CN")


class TestTranslator(unittest.TestCase):
    """Translator 工厂测试."""

    def test_create_google_free_provider(self) -> None:
        """测试创建默认 Google 免费提供者."""
        translator = Translator(provider_name="google_free")
        self.assertIsInstance(translator.provider, GoogleFreeProvider)

    def test_create_deep_l_provider(self) -> None:
        """测试创建 DeepL 提供者."""
        translator = Translator(provider_name="deep_l", api_key="k:fx", api_secret="")
        self.assertIsInstance(translator.provider, DeepLProvider)

    def test_create_tencent_provider(self) -> None:
        """测试创建腾讯云提供者."""
        translator = Translator(
            provider_name="tencent", secret_id="id", secret_key="key"
        )
        self.assertIsInstance(translator.provider, TencentProvider)

    def test_create_aliyun_provider(self) -> None:
        """测试创建阿里云提供者."""
        translator = Translator(
            provider_name="aliyun", api_key="id", api_secret="secret"
        )
        self.assertIsInstance(translator.provider, AliyunProvider)

    def test_create_translator_config_mapping(self) -> None:
        """测试 create_translator 正确映射配置字段."""
        tencent = create_translator(
            {"provider": "tencent", "api_key": "id", "api_secret": "key"}
        )
        self.assertIsInstance(tencent.provider, TencentProvider)
        self.assertEqual(tencent.provider.secret_id, "id")
        self.assertEqual(tencent.provider.secret_key, "key")

        aliyun = create_translator(
            {"provider": "aliyun", "api_key": "id", "api_secret": "secret"}
        )
        self.assertIsInstance(aliyun.provider, AliyunProvider)
        self.assertEqual(aliyun.provider.access_key_id, "id")
        self.assertEqual(aliyun.provider.access_key_secret, "secret")

        deepl = create_translator(
            {"provider": "deep_l", "api_key": "k:fx", "api_secret": ""}
        )
        self.assertIsInstance(deepl.provider, DeepLProvider)
        self.assertEqual(deepl.provider.api_key, "k:fx")

    def test_create_unknown_provider_raises(self) -> None:
        """测试未知提供者报错."""
        with self.assertRaises(ValueError):
            Translator(provider_name="unknown")

    def test_register_provider(self) -> None:
        """测试注册新提供者."""
        Translator.register_provider("mock", MockProvider)
        self.assertIn("mock", Translator.list_providers())

        translator = Translator(provider_name="mock", prefix="translated_")
        result = translator.translate("hello", "en", "zh-CN")
        self.assertEqual(result, "translated_hello")

    def test_register_invalid_provider_raises(self) -> None:
        """测试注册非提供者类报错."""
        with self.assertRaises(TypeError):
            Translator.register_provider("bad", str)

    @patch("src.translate.providers.google_free.requests.get")
    def test_translate_through_translator(self, mock_get: MagicMock) -> None:
        """测试通过 Translator 调用翻译."""
        mock_get.return_value.json.return_value = [
            [["你好", "こんにちは", None, None, 1]]
        ]
        mock_get.return_value.raise_for_status = MagicMock()

        translator = Translator()
        result = translator.translate("こんにちは", "ja", "zh-CN")
        self.assertEqual(result, "你好")


if __name__ == "__main__":
    unittest.main()
