from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import discord

from app.config import Settings
from app.database import Database
from app.models import KnowledgeSource
from app.retrieval import normalize_text
from app.safety import contains_likely_secret

logger = logging.getLogger(__name__)

IMPORTANT_KEYWORDS = (
    "deadline",
    "han nop",
    "lich hoc",
    "bat buoc",
    "thay doi",
    "huy",
    "quy dinh",
    "rubric",
)
_IMPORTANT_PATTERNS = tuple(
    re.compile(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])") for keyword in IMPORTANT_KEYWORDS
)


@dataclass(frozen=True, slots=True)
class IngestResult:
    accepted: bool
    reason: str
    source: KnowledgeSource | None = None


def is_useful_content(content: str, *, minimum_length: int = 12) -> bool:
    stripped = content.strip()
    if len(stripped) < minimum_length:
        return False
    alphanumeric_count = sum(character.isalnum() for character in stripped)
    letter_count = sum(character.isalpha() for character in stripped)
    return alphanumeric_count >= 4 and letter_count >= 2


def is_question_like(content: str) -> bool:
    return content.rstrip().endswith(("?", "？"))


def discord_source_key(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"discord:{guild_id}:{channel_id}:{message_id}"


class MessageIngestor:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    @property
    def allowed_channel_ids(self) -> frozenset[int]:
        return self.settings.qa_channel_ids | self.settings.announcement_channel_ids

    async def ingest_message(self, message: discord.Message) -> IngestResult:
        if message.guild is None:
            return IngestResult(False, "not_guild_message")
        if self.settings.guild_id and message.guild.id != self.settings.guild_id:
            return IngestResult(False, "wrong_guild")
        if isinstance(message.channel, discord.Thread) and message.channel.is_private():
            return IngestResult(False, "private_thread_not_allowed")
        if message.channel.id not in self.allowed_channel_ids:
            return IngestResult(False, "channel_not_allowed")
        if message.author.bot or message.webhook_id is not None:
            return IngestResult(False, "automated_author")
        if contains_likely_secret(message.content):
            return IngestResult(False, "likely_secret")
        if not is_useful_content(message.content):
            return IngestResult(False, "content_not_useful")
        if message.channel.id in self.settings.qa_channel_ids and is_question_like(message.content):
            return IngestResult(False, "question_not_knowledge")

        role_ids = frozenset(role.id for role in getattr(message.author, "roles", ()) if role.id)
        is_admin = bool(role_ids & self.settings.admin_role_ids)
        is_mentor = bool(role_ids & self.settings.mentor_role_ids)
        is_announcement = message.channel.id in self.settings.announcement_channel_ids
        normalized = normalize_text(message.content)
        keyword_important = any(pattern.search(normalized) for pattern in _IMPORTANT_PATTERNS)
        official = is_admin or is_mentor or is_announcement or message.pinned
        is_important = message.pinned or is_announcement or (official and keyword_important)

        priority = 20
        if is_mentor:
            priority = 70
        if message.pinned:
            priority = max(priority, 90)
        if is_admin:
            priority = max(priority, 95)
        if is_announcement:
            priority = max(priority, 100)

        source = KnowledgeSource(
            id=None,
            source_key=discord_source_key(
                message.guild.id,
                message.channel.id,
                message.id,
            ),
            source_type="discord_message",
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id,
            author_name=message.author.display_name,
            author_role_ids=role_ids,
            title=f"#{getattr(message.channel, 'name', message.channel.id)}",
            content=message.content.strip(),
            source_url=message.jump_url,
            created_at=message.created_at.isoformat(),
            edited_at=message.edited_at.isoformat() if message.edited_at else None,
            is_pinned=message.pinned,
            is_important=is_important,
            official=official,
            active=True,
            priority=priority,
        )
        persisted = await asyncio.to_thread(
            self.database.upsert_knowledge_source,
            source,
        )
        logger.debug(
            "Knowledge source upserted",
            extra={
                "source_key": persisted.source_key,
                "official": persisted.official,
                "priority": persisted.priority,
            },
        )
        return IngestResult(True, "accepted", persisted)

    async def delete_message(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
    ) -> bool:
        return await asyncio.to_thread(
            self.database.delete_discord_source,
            guild_id,
            channel_id,
            message_id,
        )
