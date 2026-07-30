from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models import KnowledgeSource


class NoteLimitReachedError(ValueError):
    """Raised when a user has reached the configured note limit."""


@dataclass(frozen=True, slots=True)
class Note:
    id: int
    user_id: int
    content: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SupportCase:
    id: int
    request_key: str
    guild_id: int
    requester_id: int
    origin_channel_id: int
    origin_message_id: int | None
    question: str
    topic: str
    routed_role_id: int | None
    support_message_id: int | None
    status: str
    created_at: str
    updated_at: str


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    author_id INTEGER,
                    author_name TEXT NOT NULL DEFAULT '',
                    author_role_ids TEXT NOT NULL DEFAULT '[]',
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    edited_at TEXT,
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    is_important INTEGER NOT NULL DEFAULT 0,
                    official INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_guild_channel
                ON knowledge_sources(guild_id, channel_id, active)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_message
                ON knowledge_sources(guild_id, channel_id, message_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS support_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_key TEXT NOT NULL UNIQUE,
                    guild_id INTEGER NOT NULL,
                    requester_id INTEGER NOT NULL,
                    origin_channel_id INTEGER NOT NULL,
                    origin_message_id INTEGER,
                    question TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT '',
                    routed_role_id INTEGER,
                    support_message_id INTEGER UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_support_status
                ON support_cases(guild_id, status, updated_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notes_user_id
                ON notes(user_id)
                """
            )

    def add_note(self, user_id: int, content: str, *, limit: int) -> Note:
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Nội dung ghi chú không được để trống")

        with closing(self._connect()) as connection, connection:
            current_count = connection.execute(
                "SELECT COUNT(*) FROM notes WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            if current_count >= limit:
                raise NoteLimitReachedError(f"Bạn chỉ được lưu tối đa {limit} ghi chú")

            cursor = connection.execute(
                "INSERT INTO notes (user_id, content) VALUES (?, ?)",
                (user_id, normalized_content),
            )
            row = connection.execute(
                """
                SELECT id, user_id, content, created_at
                FROM notes
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()

        assert row is not None
        return self._row_to_note(row)

    def list_notes(self, user_id: int, *, limit: int = 10) -> list[Note]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, content, created_at
                FROM notes
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def delete_note(self, user_id: int, note_id: int) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM notes WHERE id = ? AND user_id = ?",
                (note_id, user_id),
            )
            return cursor.rowcount > 0

    def upsert_knowledge_source(self, source: KnowledgeSource) -> KnowledgeSource:
        role_ids_json = json.dumps(sorted(source.author_role_ids))
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO knowledge_sources (
                    source_key,
                    source_type,
                    guild_id,
                    channel_id,
                    message_id,
                    author_id,
                    author_name,
                    author_role_ids,
                    title,
                    content,
                    source_url,
                    created_at,
                    edited_at,
                    is_pinned,
                    is_important,
                    official,
                    active,
                    priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_type = excluded.source_type,
                    guild_id = excluded.guild_id,
                    channel_id = excluded.channel_id,
                    message_id = excluded.message_id,
                    author_id = excluded.author_id,
                    author_name = excluded.author_name,
                    author_role_ids = excluded.author_role_ids,
                    title = excluded.title,
                    content = excluded.content,
                    source_url = excluded.source_url,
                    created_at = excluded.created_at,
                    edited_at = excluded.edited_at,
                    is_pinned = excluded.is_pinned,
                    is_important = excluded.is_important,
                    official = excluded.official,
                    active = excluded.active,
                    priority = excluded.priority
                """,
                (
                    source.source_key,
                    source.source_type,
                    source.guild_id,
                    source.channel_id,
                    source.message_id,
                    source.author_id,
                    source.author_name,
                    role_ids_json,
                    source.title,
                    source.content,
                    source.source_url,
                    source.created_at,
                    source.edited_at,
                    int(source.is_pinned),
                    int(source.is_important),
                    int(source.official),
                    int(source.active),
                    source.priority,
                ),
            )
            row = connection.execute(
                """
                SELECT *
                FROM knowledge_sources
                WHERE source_key = ?
                """,
                (source.source_key,),
            ).fetchone()

        assert row is not None
        return replace(source, id=row["id"])

    def list_knowledge_sources(
        self,
        guild_id: int,
        *,
        allowed_channel_ids: frozenset[int],
        limit: int = 2_000,
    ) -> list[KnowledgeSource]:
        parameters: list[int] = [guild_id]
        channel_filter = "channel_id IS NULL"
        if allowed_channel_ids:
            placeholders = ",".join("?" for _ in allowed_channel_ids)
            channel_filter = f"(channel_id IS NULL OR channel_id IN ({placeholders}))"
            parameters.extend(sorted(allowed_channel_ids))
        parameters.append(limit)

        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM knowledge_sources
                WHERE active = 1
                  AND (guild_id = ? OR guild_id IS NULL)
                  AND {channel_filter}
                ORDER BY priority DESC, created_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._row_to_knowledge_source(row) for row in rows]

    def get_knowledge_sources_by_keys(
        self,
        source_keys: list[str],
    ) -> list[KnowledgeSource]:
        if not source_keys:
            return []
        placeholders = ",".join("?" for _ in source_keys)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM knowledge_sources
                WHERE active = 1
                  AND source_key IN ({placeholders})
                """,
                source_keys,
            ).fetchall()
        return [self._row_to_knowledge_source(row) for row in rows]

    def delete_discord_source(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
    ) -> bool:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                DELETE FROM knowledge_sources
                WHERE source_type = 'discord_message'
                  AND guild_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                (guild_id, channel_id, message_id),
            )
            return cursor.rowcount > 0

    def cleanup_expired_sources(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                DELETE FROM knowledge_sources
                WHERE source_type = 'discord_message'
                  AND official = 0
                  AND created_at < ?
                """,
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    def cleanup_expired_support_cases(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                DELETE FROM support_cases
                WHERE status = 'resolved'
                  AND updated_at < ?
                """,
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    def create_support_case(
        self,
        *,
        request_key: str,
        guild_id: int,
        requester_id: int,
        origin_channel_id: int,
        origin_message_id: int | None,
        question: str,
        topic: str,
        routed_role_id: int | None,
    ) -> SupportCase:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO support_cases (
                    request_key,
                    guild_id,
                    requester_id,
                    origin_channel_id,
                    origin_message_id,
                    question,
                    topic,
                    routed_role_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_key) DO NOTHING
                """,
                (
                    request_key,
                    guild_id,
                    requester_id,
                    origin_channel_id,
                    origin_message_id,
                    question,
                    topic,
                    routed_role_id,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM support_cases WHERE request_key = ?",
                (request_key,),
            ).fetchone()

        assert row is not None
        return self._row_to_support_case(row)

    def attach_support_message(
        self,
        case_id: int,
        support_message_id: int,
    ) -> SupportCase:
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE support_cases
                SET support_message_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (support_message_id, now, case_id),
            )
            row = connection.execute(
                "SELECT * FROM support_cases WHERE id = ?",
                (case_id,),
            ).fetchone()

        assert row is not None
        return self._row_to_support_case(row)

    def get_support_case_by_message(
        self,
        support_message_id: int,
    ) -> SupportCase | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM support_cases
                WHERE support_message_id = ?
                """,
                (support_message_id,),
            ).fetchone()
        return self._row_to_support_case(row) if row is not None else None

    def update_support_status(
        self,
        support_message_id: int,
        status: str,
    ) -> SupportCase | None:
        if status not in {"pending", "viewing", "resolved"}:
            raise ValueError("Trạng thái support không hợp lệ")

        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE support_cases
                SET status = ?, updated_at = ?
                WHERE support_message_id = ?
                """,
                (status, now, support_message_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT *
                FROM support_cases
                WHERE support_message_id = ?
                """,
                (support_message_id,),
            ).fetchone()

        assert row is not None
        return self._row_to_support_case(row)

    @staticmethod
    def _row_to_note(row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            user_id=row["user_id"],
            content=row["content"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_knowledge_source(row: sqlite3.Row) -> KnowledgeSource:
        return KnowledgeSource(
            id=row["id"],
            source_key=row["source_key"],
            source_type=row["source_type"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            author_role_ids=frozenset(json.loads(row["author_role_ids"])),
            title=row["title"],
            content=row["content"],
            source_url=row["source_url"],
            created_at=row["created_at"],
            edited_at=row["edited_at"],
            is_pinned=bool(row["is_pinned"]),
            is_important=bool(row["is_important"]),
            official=bool(row["official"]),
            active=bool(row["active"]),
            priority=row["priority"],
        )

    @staticmethod
    def _row_to_support_case(row: sqlite3.Row) -> SupportCase:
        return SupportCase(
            id=row["id"],
            request_key=row["request_key"],
            guild_id=row["guild_id"],
            requester_id=row["requester_id"],
            origin_channel_id=row["origin_channel_id"],
            origin_message_id=row["origin_message_id"],
            question=row["question"],
            topic=row["topic"],
            routed_role_id=row["routed_role_id"],
            support_message_id=row["support_message_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
