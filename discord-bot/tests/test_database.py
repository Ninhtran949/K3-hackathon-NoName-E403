import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.database import Database, NoteLimitReachedError
from app.models import KnowledgeSource


def make_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "bot.db")
    database.initialize()
    return database


def make_source(
    key: str,
    *,
    guild_id: int | None = 1,
    channel_id: int | None = 10,
    message_id: int | None = 100,
    created_at: str = "2026-07-30T09:00:00+00:00",
    active: bool = True,
    official: bool = False,
    priority: int = 0,
) -> KnowledgeSource:
    return KnowledgeSource(
        source_key=key,
        source_type="discord_message" if message_id is not None else "static_document",
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
        author_id=42,
        author_name="BTC",
        author_role_ids=frozenset({7, 8}),
        title="Thông báo",
        content=f"Nội dung của {key}",
        source_url=f"https://discord.test/{key}",
        created_at=created_at,
        official=official,
        active=active,
        priority=priority,
    )


def test_add_and_list_notes(tmp_path: Path) -> None:
    database = make_database(tmp_path)

    first = database.add_note(100, "Ghi chú thứ nhất", limit=10)
    second = database.add_note(100, "Ghi chú thứ hai", limit=10)
    database.add_note(200, "Ghi chú của người khác", limit=10)

    notes = database.list_notes(100)

    assert [note.id for note in notes] == [second.id, first.id]
    assert [note.content for note in notes] == [
        "Ghi chú thứ hai",
        "Ghi chú thứ nhất",
    ]


def test_delete_only_owners_note(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    note = database.add_note(100, "Thông tin riêng", limit=10)

    assert database.delete_note(200, note.id) is False
    assert database.delete_note(100, note.id) is True
    assert database.list_notes(100) == []


def test_note_limit(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    database.add_note(100, "Ghi chú duy nhất", limit=1)

    with pytest.raises(NoteLimitReachedError):
        database.add_note(100, "Vượt giới hạn", limit=1)


def test_upsert_knowledge_source_round_trips_and_updates_in_place(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    inserted = database.upsert_knowledge_source(make_source("discord:1:10:100"))

    assert inserted.id is not None
    assert inserted.author_role_ids == frozenset({7, 8})

    updated = database.upsert_knowledge_source(
        replace(
            inserted,
            content="Deadline mới là 23:59 ngày 16/08.",
            author_role_ids=frozenset({9}),
            edited_at="2026-07-30T10:00:00+00:00",
            is_pinned=True,
            is_important=True,
            official=True,
            priority=95,
        )
    )

    assert updated.id == inserted.id
    loaded = database.get_knowledge_sources_by_keys([inserted.source_key])
    assert len(loaded) == 1
    assert loaded[0] == updated


def test_list_knowledge_sources_enforces_guild_channel_and_active_filters(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    sources = [
        make_source("allowed", channel_id=10, priority=5),
        make_source("private", channel_id=11, priority=100),
        make_source("other-guild", guild_id=2, channel_id=10),
        make_source("inactive", channel_id=10, active=False),
        make_source("guild-static", channel_id=None, message_id=None),
        make_source("global-static", guild_id=None, channel_id=None, message_id=None),
    ]
    for item in sources:
        database.upsert_knowledge_source(item)

    visible = database.list_knowledge_sources(1, allowed_channel_ids=frozenset({10}))

    assert {item.source_key for item in visible} == {
        "allowed",
        "guild-static",
        "global-static",
    }
    static_only = database.list_knowledge_sources(1, allowed_channel_ids=frozenset())
    assert {item.source_key for item in static_only} == {
        "guild-static",
        "global-static",
    }


def test_list_knowledge_sources_is_ordered_and_limited(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    database.upsert_knowledge_source(make_source("low", priority=1))
    database.upsert_knowledge_source(make_source("high", message_id=101, priority=10))

    loaded = database.list_knowledge_sources(
        1,
        allowed_channel_ids=frozenset({10}),
        limit=1,
    )

    assert [item.source_key for item in loaded] == ["high"]


def test_delete_discord_source_is_scoped_to_exact_message(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    stored = database.upsert_knowledge_source(make_source("discord:1:10:100"))

    assert database.delete_discord_source(1, 99, 100) is False
    assert database.get_knowledge_sources_by_keys([stored.source_key]) != []
    assert database.delete_discord_source(1, 10, 100) is True
    assert database.get_knowledge_sources_by_keys([stored.source_key]) == []
    assert database.delete_discord_source(1, 10, 100) is False


def test_cleanup_expired_sources_preserves_official_static_and_recent(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    now = datetime.now(UTC)
    old = (now - timedelta(days=40)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()
    database.upsert_knowledge_source(make_source("expired", created_at=old))
    database.upsert_knowledge_source(
        make_source("official-old", message_id=101, created_at=old, official=True)
    )
    database.upsert_knowledge_source(
        make_source("static-old", channel_id=None, message_id=None, created_at=old)
    )
    database.upsert_knowledge_source(make_source("recent", message_id=102, created_at=recent))

    assert database.cleanup_expired_sources(30) == 1
    remaining = database.get_knowledge_sources_by_keys(
        ["expired", "official-old", "static-old", "recent"]
    )
    assert {item.source_key for item in remaining} == {
        "official-old",
        "static-old",
        "recent",
    }


def test_support_case_lifecycle_and_idempotent_creation(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    created = database.create_support_case(
        request_key="interaction:123",
        guild_id=1,
        requester_id=2,
        origin_channel_id=10,
        origin_message_id=20,
        question="Deadline Project 1 là khi nào?",
        topic="deadline",
        routed_role_id=30,
    )
    duplicate = database.create_support_case(
        request_key="interaction:123",
        guild_id=999,
        requester_id=999,
        origin_channel_id=999,
        origin_message_id=None,
        question="Nội dung không được ghi đè",
        topic="other",
        routed_role_id=None,
    )

    assert duplicate == created
    assert created.status == "pending"
    assert created.support_message_id is None

    attached = database.attach_support_message(created.id, 456)
    assert attached.support_message_id == 456
    assert database.get_support_case_by_message(456) == attached

    viewing = database.update_support_status(456, "viewing")
    assert viewing is not None
    assert viewing.status == "viewing"
    resolved = database.update_support_status(456, "resolved")
    assert resolved is not None
    assert resolved.status == "resolved"

    assert database.get_support_case_by_message(999) is None
    assert database.update_support_status(999, "resolved") is None
    with pytest.raises(ValueError, match="support"):
        database.update_support_status(456, "closed")


def test_cleanup_support_cases_only_deletes_old_resolved_cases(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    old_resolved = database.create_support_case(
        request_key="old-resolved",
        guild_id=1,
        requester_id=2,
        origin_channel_id=10,
        origin_message_id=None,
        question="Câu hỏi đã xử lý",
        topic="other",
        routed_role_id=None,
    )
    old_pending = database.create_support_case(
        request_key="old-pending",
        guild_id=1,
        requester_id=3,
        origin_channel_id=10,
        origin_message_id=None,
        question="Câu hỏi vẫn đang chờ",
        topic="other",
        routed_role_id=None,
    )
    database.attach_support_message(old_resolved.id, 501)
    database.attach_support_message(old_pending.id, 502)
    database.update_support_status(501, "resolved")

    old_timestamp = (datetime.now(UTC) - timedelta(days=120)).isoformat()
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE support_cases SET updated_at = ? WHERE id IN (?, ?)",
            (old_timestamp, old_resolved.id, old_pending.id),
        )

    assert database.cleanup_expired_support_cases(90) == 1
    assert database.get_support_case_by_message(501) is None
    pending = database.get_support_case_by_message(502)
    assert pending is not None
    assert pending.status == "pending"
