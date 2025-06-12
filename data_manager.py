# data_manager.py
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from logger import get_logger
import config
import json
from collections import Counter

logger = get_logger()


class DataManager:
    def __init__(self, db_path: str = config.DATABASE_URL):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = self._create_connection()
        self._create_tables()
        logger.info(f"DataManager инициализирован с базой данных: {db_path}")

    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Создает подключение к базе данных SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Ошибка при подключении к базе данных: {e}")
            return None

    def _create_tables(self):
        """Создает таблицы в базе данных, если они не существуют."""
        if not self.conn:
            return
        try:
            with self.conn:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY,
                        channel_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        date TEXT NOT NULL
                    );
                """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analyses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL UNIQUE,
                        summary TEXT NOT NULL,
                        sentiment TEXT NOT NULL,
                        hashtags TEXT, -- JSON-строка
                        analysis_date TEXT NOT NULL,
                        FOREIGN KEY (message_id) REFERENCES messages (id)
                    );
                """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS last_processed_ids (
                        channel_id TEXT PRIMARY KEY,
                        last_message_id INTEGER NOT NULL
                    );
                    """
                )
                logger.info(
                    "Таблицы 'messages', 'analyses' и 'last_processed_ids' успешно проверены/созданы."
                )
        except sqlite3.Error as e:
            logger.error(f"Ошибка при создании таблиц: {e}")

    def save_message(self, message: Dict[str, Any]):
        """Сохраняет одно сообщение в базу данных."""
        if not self.conn:
            return
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR IGNORE INTO messages (id, channel_id, text, date) VALUES (?, ?, ?, ?)",
                    (
                        message["id"],
                        message.get("channel_id", ""),
                        message["text"],
                        message["date"],
                    ),
                )
        except sqlite3.Error as e:
            logger.error(f"Ошибка при сохранении сообщения {message.get('id')}: {e}")

    def save_analysis(self, message_id: int, analysis: Dict[str, Any]):
        """Сохраняет результаты анализа в базу данных."""
        if not self.conn:
            return

        if not isinstance(analysis, dict):
            analysis = analysis.dict()

        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO analyses (message_id, summary, sentiment, hashtags, analysis_date)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        analysis.get("summary", ""),
                        analysis.get("sentiment", ""),
                        json.dumps(analysis.get("hashtags", [])),
                        datetime.now().isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            logger.error(
                f"Ошибка при сохранении анализа для сообщения {message_id}: {e}"
            )

    def get_last_message_id(self, channel_id: str) -> int:
        """Возвращает ID последнего обработанного сообщения для указанного канала из таблицы 'last_processed_ids'."""
        if not self.conn:
            return 0
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT last_message_id FROM last_processed_ids WHERE channel_id = ?",
                (channel_id,),
            )
            result = cursor.fetchone()
            return result["last_message_id"] if result else 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении последнего ID сообщения из кэша: {e}")
            return 0

    def set_last_message_id(self, channel_id: str, last_message_id: int):
        """Сохраняет ID последнего обработанного сообщения для канала."""
        if not self.conn:
            return
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO last_processed_ids (channel_id, last_message_id)
                    VALUES (?, ?)
                    ON CONFLICT(channel_id) DO UPDATE SET last_message_id = excluded.last_message_id;
                    """,
                    (channel_id, last_message_id),
                )
        except sqlite3.Error as e:
            logger.error(
                f"Ошибка при сохранении последнего ID сообщения для канала {channel_id}: {e}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику анализа из базы данных."""
        if not self.conn:
            return {}
        try:
            with self.conn:
                total_messages = self.conn.execute(
                    "SELECT COUNT(id) FROM analyses"
                ).fetchone()[0]
                sentiment_counts = self.conn.execute(
                    "SELECT sentiment, COUNT(id) FROM analyses GROUP BY sentiment"
                ).fetchall()

                cursor = self.conn.cursor()
                cursor.execute("SELECT hashtags FROM analyses")
                rows = cursor.fetchall()

                all_hashtags = []
                for row in rows:
                    all_hashtags.extend(json.loads(row["hashtags"] or "[]"))

                hashtag_counts = Counter(all_hashtags).most_common(10)

                stats = {
                    "total_messages": total_messages,
                    "sentiment_counts": {
                        row["sentiment"]: row[1] for row in sentiment_counts
                    },
                    "popular_hashtags": [tag for tag, count in hashtag_counts],
                }
                return stats
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {}

    def close(self):
        """Закрывает соединение с базой данных."""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с базой данных закрыто.")
