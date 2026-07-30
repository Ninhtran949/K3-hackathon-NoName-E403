"""SQLite-backed first-question tracker."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ....domain import MessageInput


class SqliteLearnerActivityAdapter:
    """Persist one first-question marker per learner and Discord channel."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def claim_first_question(self, message: MessageInput) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO learner_first_questions (
                    author_id,
                    channel_id,
                    first_message_id,
                    first_seen_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    message.author_id,
                    message.channel_id,
                    message.message_id,
                    message.created_at.isoformat(),
                ),
            )
            return cursor.rowcount == 1

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learner_first_questions (
                    author_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    first_message_id TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    PRIMARY KEY (author_id, channel_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
