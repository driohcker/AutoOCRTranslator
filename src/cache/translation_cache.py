"""缓存模块，基于 SQLite.

提供翻译结果的持久化缓存，避免重复调用翻译 API.
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TranslationCache:
    """翻译缓存.

    使用 SQLite 存储原文到译文的映射，支持命中统计和 TTL 过期清理.
    """

    def __init__(self, db_path: str = "data/cache/translations.db"):
        """初始化缓存.

        Args:
            db_path: SQLite 数据库文件路径.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """创建并管理 SQLite 连接上下文，确保连接正确关闭.

        启用 WAL 日志模式 + busy_timeout，支持主进程（读）与
        翻译子进程（读写）跨进程并发访问同一数据库。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化数据库表结构."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hit_count INTEGER DEFAULT 0,
                    UNIQUE(source_text, source_lang, target_lang)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_translation_lookup
                ON translations(source_text, source_lang, target_lang)
                """
            )
            conn.commit()

    def get(
        self, text: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """查询缓存.

        Args:
            text: 原文.
            source_lang: 源语言代码.
            target_lang: 目标语言代码.

        Returns:
            缓存的译文，未命中返回 None.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id, translation FROM translations
                WHERE source_text = ? AND source_lang = ? AND target_lang = ?
                """,
                (text, source_lang, target_lang),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            cache_id, translation = row
            conn.execute(
                """
                UPDATE translations
                SET hit_count = hit_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (cache_id,),
            )
            conn.commit()
            return translation

    def set(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation: str,
    ) -> None:
        """写入缓存.

        如果记录已存在，则更新译文、访问时间和命中次数.

        Args:
            text: 原文.
            source_lang: 源语言代码.
            target_lang: 目标语言代码.
            translation: 译文.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO translations
                (source_text, source_lang, target_lang, translation)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_text, source_lang, target_lang)
                DO UPDATE SET
                    translation = excluded.translation,
                    last_accessed = CURRENT_TIMESTAMP,
                    hit_count = hit_count + 1
                """,
                (text, source_lang, target_lang, translation),
            )
            conn.commit()

    def clear(self) -> None:
        """清空所有缓存."""
        with self._connect() as conn:
            conn.execute("DELETE FROM translations")
            conn.commit()
        logger.info("翻译缓存已清空")

    def cleanup_expired(self, ttl_days: int) -> int:
        """清理过期缓存.

        Args:
            ttl_days: 缓存有效期（天）。<= 0 表示永不过期。

        Returns:
            清理的记录数.
        """
        if ttl_days <= 0:
            return 0

        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM translations
                WHERE last_accessed < datetime('now', ?)
                """,
                (f"-{ttl_days} days",),
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条过期翻译缓存")
            return deleted

    def stats(self) -> dict:
        """获取缓存统计信息.

        Returns:
            {"count": 记录总数, "total_hits": 总命中次数}
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM translations"
            )
            total, total_hits = cursor.fetchone()
            return {"count": total, "total_hits": total_hits}
