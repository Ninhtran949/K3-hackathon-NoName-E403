from __future__ import annotations

import aiosqlite
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT,
    channel_id TEXT,
    message_id TEXT UNIQUE,
    author_id TEXT,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class QuestionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def add_pending(
        self,
        *,
        guild_id: str | None,
        channel_id: str,
        message_id: str,
        author_id: str,
        question: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO pending_questions
                (guild_id, channel_id, message_id, author_id, question, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
                """,
                (guild_id, channel_id, message_id, author_id, question),
            )
            await db.commit()

    async def mark_resolved(self, message_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE pending_questions
                SET status = 'Resolved', updated_at = datetime('now')
                WHERE message_id = ?
                """,
                (message_id,),
            )
            await db.commit()

    async def mark_resolved_by_id(self, row_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM pending_questions WHERE id = ?",
                (row_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            await db.execute(
                """
                UPDATE pending_questions
                SET status = 'Resolved', updated_at = datetime('now')
                WHERE id = ?
                """,
                (row_id,),
            )
            await db.commit()
            return dict(row)

    async def list_stale(self, hours: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM pending_questions
                WHERE status = 'Pending'
                  AND datetime(created_at) <= datetime('now', ?)
                ORDER BY created_at ASC
                """,
                (f"-{hours} hours",),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def mark_escalated(self, message_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE pending_questions
                SET status = 'Escalated', updated_at = datetime('now')
                WHERE message_id = ?
                """,
                (message_id,),
            )
            await db.commit()

    async def list_open(self, *, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM pending_questions
                WHERE status IN ('Pending', 'Escalated')
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_by_status(self) -> dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT status, COUNT(*) AS n
                FROM pending_questions
                GROUP BY status
                """
            )
            rows = await cur.fetchall()
            return {str(status): int(n) for status, n in rows}

    async def resolve_latest_for_author(self, author_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM pending_questions
                WHERE author_id = ? AND status IN ('Pending', 'Escalated')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (author_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
            await db.execute(
                """
                UPDATE pending_questions
                SET status = 'Resolved', updated_at = datetime('now')
                WHERE id = ?
                """,
                (data["id"],),
            )
            await db.commit()
            return data
