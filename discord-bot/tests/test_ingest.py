from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.database import Database
from app.ingest import (
    MessageIngestor,
    discord_source_key,
    is_question_like,
    is_useful_content,
)


def make_settings(tmp_path: Path) -> Settings:
    return Settings.from_env(
        {
            "DISCORD_TOKEN": "test-token",
            "DISCORD_GUILD_ID": "1",
            "DISCORD_QA_CHANNEL_IDS": "10",
            "DISCORD_ANNOUNCEMENT_CHANNEL_IDS": "20",
            "DISCORD_ADMIN_ROLE_IDS": "100",
            "DISCORD_MENTOR_ROLE_IDS": "200",
            "DATABASE_PATH": str(tmp_path / "bot.db"),
        },
        base_dir=tmp_path,
    )


def make_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "bot.db")
    database.initialize()
    return database


def make_message(
    *,
    message_id: int = 1000,
    guild_id: int | None = 1,
    channel_id: int = 10,
    content: str = "Deadline Project 1 là ngày 15/08.",
    author_id: int = 50,
    role_ids: tuple[int, ...] = (),
    author_bot: bool = False,
    webhook_id: int | None = None,
    pinned: bool = False,
    edited_at: datetime | None = None,
) -> SimpleNamespace:
    guild = SimpleNamespace(id=guild_id) if guild_id is not None else None
    channel = SimpleNamespace(id=channel_id, name=f"channel-{channel_id}")
    author = SimpleNamespace(
        id=author_id,
        display_name=f"User {author_id}",
        bot=author_bot,
        roles=[SimpleNamespace(id=role_id) for role_id in role_ids],
    )
    return SimpleNamespace(
        id=message_id,
        guild=guild,
        channel=channel,
        author=author,
        webhook_id=webhook_id,
        content=content,
        pinned=pinned,
        jump_url=f"https://discord.test/channels/{guild_id}/{channel_id}/{message_id}",
        created_at=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        edited_at=edited_at,
    )


class RejectWriteDatabase:
    def upsert_knowledge_source(self, source: object) -> object:
        raise AssertionError(f"Rejected message unexpectedly persisted: {source!r}")


@pytest.mark.parametrize(
    "content",
    [
        "",
        "quá ngắn",
        "🎉🚀✅🔥🎉🚀✅🔥🎉🚀✅🔥",
        "____________",
    ],
)
def test_is_useful_content_rejects_empty_short_or_symbol_only(content: str) -> None:
    assert not is_useful_content(content)


def test_is_useful_content_accepts_meaningful_vietnamese() -> None:
    assert is_useful_content("Deadline nộp bài là ngày 15/08.")


def test_question_like_only_matches_trailing_question_mark() -> None:
    assert is_question_like("Deadline là khi nào?")
    assert is_question_like("Deadline là khi nào？  ")
    assert not is_question_like("Deadline là ngày 15/08.")


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        (make_message(guild_id=None), "not_guild_message"),
        (make_message(guild_id=2), "wrong_guild"),
        (make_message(channel_id=99), "channel_not_allowed"),
        (make_message(author_bot=True), "automated_author"),
        (make_message(webhook_id=123), "automated_author"),
        (
            make_message(content="ANTHROPIC_API_KEY=sk-ant-examplecredential123456789"),
            "likely_secret",
        ),
        (make_message(content="👍👍"), "content_not_useful"),
        (
            make_message(content="Deadline Project 1 là khi nào?"),
            "question_not_knowledge",
        ),
    ],
)
def test_ingest_rejects_messages_outside_policy(
    tmp_path: Path,
    message: SimpleNamespace,
    reason: str,
) -> None:
    ingestor = MessageIngestor(RejectWriteDatabase(), make_settings(tmp_path))  # type: ignore[arg-type]

    result = asyncio.run(ingestor.ingest_message(message))

    assert result.accepted is False
    assert result.reason == reason
    assert result.source is None


def test_ingest_persists_regular_message_with_source_metadata(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    ingestor = MessageIngestor(database, make_settings(tmp_path))
    message = make_message(
        content="Mọi người chia sẻ kinh nghiệm làm Project 1 nhé.",
        role_ids=(300,),
    )

    result = asyncio.run(ingestor.ingest_message(message))

    assert result.accepted is True
    assert result.reason == "accepted"
    assert result.source is not None
    assert result.source.id is not None
    assert result.source.source_key == discord_source_key(1, 10, 1000)
    assert result.source.author_role_ids == frozenset({300})
    assert result.source.title == "#channel-10"
    assert result.source.content == message.content
    assert result.source.created_at == message.created_at.isoformat()
    assert result.source.official is False
    assert result.source.is_important is False
    assert result.source.priority == 20


@pytest.mark.parametrize(
    ("channel_id", "role_ids", "pinned", "priority"),
    [
        (10, (200,), False, 70),
        (10, (), True, 90),
        (10, (100,), False, 95),
        (20, (), False, 100),
    ],
)
def test_ingest_assigns_official_importance_and_priority(
    tmp_path: Path,
    channel_id: int,
    role_ids: tuple[int, ...],
    pinned: bool,
    priority: int,
) -> None:
    database = make_database(tmp_path)
    ingestor = MessageIngestor(database, make_settings(tmp_path))
    message = make_message(
        channel_id=channel_id,
        role_ids=role_ids,
        pinned=pinned,
    )

    result = asyncio.run(ingestor.ingest_message(message))

    assert result.source is not None
    assert result.source.official is True
    assert result.source.is_important is True
    assert result.source.priority == priority


def test_important_keyword_matches_whole_word_not_author_name_fragment(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    ingestor = MessageIngestor(database, make_settings(tmp_path))
    message = make_message(
        role_ids=(200,),
        content="Mentor Huyền chia sẻ tài liệu tham khảo cho Project 1.",
    )

    result = asyncio.run(ingestor.ingest_message(message))

    assert result.source is not None
    assert result.source.official is True
    assert result.source.is_important is False


def test_reingest_edit_updates_same_source_and_delete_removes_it(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    ingestor = MessageIngestor(database, make_settings(tmp_path))
    original = make_message(content="Deadline Project 1 là ngày 15/08.")
    first = asyncio.run(ingestor.ingest_message(original))
    edited_at = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    edited = make_message(
        content="Deadline Project 1 đổi thành ngày 16/08.",
        edited_at=edited_at,
    )

    second = asyncio.run(ingestor.ingest_message(edited))

    assert first.source is not None
    assert second.source is not None
    assert second.source.id == first.source.id
    assert second.source.content == edited.content
    assert second.source.edited_at == edited_at.isoformat()
    assert len(database.list_knowledge_sources(1, allowed_channel_ids=frozenset({10}))) == 1

    assert asyncio.run(ingestor.delete_message(1, 99, 1000)) is False
    assert asyncio.run(ingestor.delete_message(1, 10, 1000)) is True
    assert database.get_knowledge_sources_by_keys([second.source.source_key]) == []
