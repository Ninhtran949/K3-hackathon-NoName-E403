"""SQLite persistence for escalation review and digest state."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ....domain import AnswerSource, EscalationRecord, MentorDraft


class SqliteSupportRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create(self, record: EscalationRecord) -> None:
        sources = [
            {
                "document_id": source.document_id,
                "title": source.title,
                "source_url": source.source_url,
            }
            for source in (record.draft.sources if record.draft else ())
        ]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO escalation_reviews (
                    review_id, question, author_id, author_mention,
                    original_channel_id, original_message_id, source_url,
                    mentor_mention, created_at, draft_text,
                    draft_sources_json, draft_caveats_json,
                    support_context_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    record.review_id,
                    record.question,
                    record.author_id,
                    record.author_mention,
                    record.original_channel_id,
                    record.original_message_id,
                    record.source_url,
                    record.mentor_mention,
                    record.created_at.isoformat(),
                    record.draft.text if record.draft else "",
                    json.dumps(sources, ensure_ascii=False),
                    json.dumps(
                        list(record.draft.caveats) if record.draft else [],
                        ensure_ascii=False,
                    ),
                    record.support_context_id,
                ),
            )

    def bind_context(self, review_id: str, support_context_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE escalation_reviews
                SET support_context_id = ?
                WHERE review_id = ? AND status = 'pending'
                """,
                (support_context_id, review_id),
            )
            return cursor.rowcount == 1

    def find(
        self,
        *,
        review_id: str = "",
        support_context_id: str = "",
    ) -> EscalationRecord | None:
        if not review_id and not support_context_id:
            return None
        column = "review_id" if review_id else "support_context_id"
        value = review_id or support_context_id
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"""
                SELECT * FROM escalation_reviews
                WHERE {column} = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (value,),
            ).fetchone()
        return self._to_record(row) if row else None

    def status(self, review_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM escalation_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        return str(row[0]) if row else ""

    def claim_for_delivery(self, review_id: str) -> bool:
        return self._transition(review_id, "pending", "sending")

    def mark_sent(self, review_id: str) -> None:
        self._transition(review_id, "sending", "sent")

    def restore_pending(self, review_id: str) -> None:
        self._transition(review_id, "sending", "pending")

    def mark_rejected(self, review_id: str) -> bool:
        return self._transition(review_id, "pending", "rejected")

    def list_pending(self, limit: int) -> tuple[EscalationRecord, ...]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT * FROM escalation_reviews
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (max(0, limit),),
            ).fetchall()
        return tuple(self._to_record(row) for row in rows)

    def last_digest_date(self) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM support_state WHERE key = 'last_digest_date'"
            ).fetchone()
        return str(row[0]) if row else ""

    def mark_digest_sent(self, report_date: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO support_state (key, value)
                VALUES ('last_digest_date', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (report_date,),
            )

    def _transition(self, review_id: str, old: str, new: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE escalation_reviews
                SET status = ?
                WHERE review_id = ? AND status = ?
                """,
                (new, review_id, old),
            )
            return cursor.rowcount == 1

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS escalation_reviews (
                    review_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    author_mention TEXT NOT NULL,
                    original_channel_id TEXT NOT NULL,
                    original_message_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    mentor_mention TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    draft_text TEXT NOT NULL,
                    draft_sources_json TEXT NOT NULL,
                    draft_caveats_json TEXT NOT NULL,
                    support_context_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reviews_context
                    ON escalation_reviews (support_context_id);
                CREATE INDEX IF NOT EXISTS idx_reviews_status_created
                    ON escalation_reviews (status, created_at);
                CREATE TABLE IF NOT EXISTS support_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _to_record(row: sqlite3.Row) -> EscalationRecord:
        sources = tuple(
            AnswerSource(
                document_id=str(item["document_id"]),
                title=str(item["title"]),
                source_url=str(item["source_url"]),
            )
            for item in json.loads(row["draft_sources_json"])
        )
        caveats = tuple(str(item) for item in json.loads(row["draft_caveats_json"]))
        draft_text = str(row["draft_text"])
        draft = (
            MentorDraft(text=draft_text, sources=sources, caveats=caveats)
            if draft_text
            else None
        )
        return EscalationRecord(
            review_id=str(row["review_id"]),
            question=str(row["question"]),
            author_id=str(row["author_id"]),
            author_mention=str(row["author_mention"]),
            original_channel_id=str(row["original_channel_id"]),
            original_message_id=str(row["original_message_id"]),
            source_url=str(row["source_url"]),
            mentor_mention=str(row["mentor_mention"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            draft=draft,
            support_context_id=str(row["support_context_id"]),
        )
