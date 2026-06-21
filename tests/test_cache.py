"""缓存模块测试."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.cache.translation_cache import TranslationCache


class TestTranslationCache(unittest.TestCase):
    """TranslationCache 单元测试."""

    def setUp(self) -> None:
        """每个测试前创建独立临时数据库."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_cache.db"
        self.cache = TranslationCache(str(self.db_path))

    def tearDown(self) -> None:
        """每个测试后清理临时数据库."""
        self.tmp_dir.cleanup()

    def test_set_and_get(self) -> None:
        """测试写入和读取缓存."""
        self.cache.set("hello", "en", "zh-CN", "你好")
        result = self.cache.get("hello", "en", "zh-CN")
        self.assertEqual(result, "你好")

    def test_get_nonexistent_returns_none(self) -> None:
        """测试未命中返回 None."""
        result = self.cache.get("nonexistent", "ja", "zh-CN")
        self.assertIsNone(result)

    def test_hit_count_increments_on_get(self) -> None:
        """测试命中时命中次数增加."""
        self.cache.set("hello", "en", "zh-CN", "你好")
        self.cache.get("hello", "en", "zh-CN")
        self.cache.get("hello", "en", "zh-CN")

        stats = self.cache.stats()
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["total_hits"], 2)

    def test_update_existing_translation(self) -> None:
        """测试重复写入会更新译文."""
        self.cache.set("hello", "en", "zh-CN", "你好")
        self.cache.set("hello", "en", "zh-CN", "您好")
        result = self.cache.get("hello", "en", "zh-CN")
        self.assertEqual(result, "您好")

    def test_clear(self) -> None:
        """测试清空缓存."""
        self.cache.set("a", "ja", "zh-CN", "A")
        self.cache.set("b", "ja", "zh-CN", "B")
        self.cache.clear()

        self.assertIsNone(self.cache.get("a", "ja", "zh-CN"))
        self.assertIsNone(self.cache.get("b", "ja", "zh-CN"))
        self.assertEqual(self.cache.stats()["count"], 0)

    def test_cleanup_expired(self) -> None:
        """测试过期清理."""
        self.cache.set("recent", "ja", "zh-CN", "最近")

        # 手动将一条记录设为很久以前访问
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE translations
                SET last_accessed = datetime('now', '-10 days')
                WHERE source_text = ?
                """,
                ("recent",),
            )
            conn.commit()

        deleted = self.cache.cleanup_expired(ttl_days=7)
        self.assertEqual(deleted, 1)
        self.assertIsNone(self.cache.get("recent", "ja", "zh-CN"))

    def test_cleanup_expired_disabled_with_zero_ttl(self) -> None:
        """测试 TTL=0 时不清理."""
        self.cache.set("old", "ja", "zh-CN", "旧")

        # 手动将记录设为很久以前访问
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE translations
                SET last_accessed = datetime('now', '-100 days')
                WHERE source_text = ?
                """,
                ("old",),
            )
            conn.commit()

        deleted = self.cache.cleanup_expired(ttl_days=0)
        self.assertEqual(deleted, 0)
        self.assertEqual(self.cache.get("old", "ja", "zh-CN"), "旧")

    def test_stats(self) -> None:
        """测试统计信息."""
        self.cache.set("x", "ja", "zh-CN", "X")
        self.cache.set("y", "en", "zh-CN", "Y")
        self.cache.get("x", "ja", "zh-CN")

        stats = self.cache.stats()
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["total_hits"], 1)

    def test_different_language_pairs_are_independent(self) -> None:
        """测试不同语言对互相独立."""
        self.cache.set("hello", "en", "zh-CN", "你好")
        self.cache.set("hello", "en", "ja", "こんにちは")

        self.assertEqual(
            self.cache.get("hello", "en", "zh-CN"), "你好"
        )
        self.assertEqual(
            self.cache.get("hello", "en", "ja"), "こんにちは"
        )


if __name__ == "__main__":
    unittest.main()
