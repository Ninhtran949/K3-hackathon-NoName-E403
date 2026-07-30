"""Discord delivery adapter: event mapping and response delivery only."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

import discord

from ...core_rag_engine.domain import (
    MentorDecisionInput,
    MessageInput,
    OutcomeKind,
    ProcessingResult,
    ReviewAction,
    ReviewDecisionKind,
)
from ...core_rag_engine.ports.inbound import RAGEnginePort, SupportWorkflowPort
from .formatter import (
    format_answer,
    format_approved_answer,
    format_digest,
    format_escalation,
    format_support_ticket,
)

logger = logging.getLogger(__name__)


class K3MateDiscordClient(discord.Client):
    def __init__(
        self,
        *,
        engine: RAGEnginePort,
        support_workflow: SupportWorkflowPort,
        monitored_channel_ids: frozenset[int],
        support_channel_id: int,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._engine = engine
        self._support_workflow = support_workflow
        self._monitored_channel_ids = monitored_channel_ids
        self._support_channel_id = support_channel_id
        self._allowed_mentions = discord.AllowedMentions(
            everyone=False,
            users=True,
            roles=True,
            replied_user=False,
        )
        self._digest_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        self._digest_task = asyncio.create_task(
            self._digest_worker(),
            name="k3-mate-digest",
        )

    async def close(self) -> None:
        if self._digest_task:
            self._digest_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._digest_task
        await super().close()

    async def on_ready(self) -> None:
        logger.info(
            "Discord bot ready as %s; monitoring %s",
            self.user,
            sorted(self._monitored_channel_ids),
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self._is_support_context(message.channel):
            if message.content.strip() == "!digest":
                await self._send_digest(force=True, acknowledgement=message)
                return
            command = _parse_review_command(message.content)
            if command:
                await self._handle_review_command(message, *command)
            return
        if message.channel.id not in self._monitored_channel_ids:
            return

        domain_message = MessageInput(
            message_id=str(message.id),
            content=message.content,
            author_id=str(message.author.id),
            author_mention=message.author.mention,
            channel_id=str(message.channel.id),
            source_url=message.jump_url,
            created_at=message.created_at.astimezone(UTC),
            is_bot=False,
        )

        try:
            result = await asyncio.to_thread(
                self._engine.handle_message,
                domain_message,
            )
        except Exception:
            logger.exception("Failed to process Discord message %s", message.id)
            await message.reply(
                "Mình đang gặp lỗi xử lý tạm thời. Mentor/BTC vui lòng kiểm tra log.",
                mention_author=False,
            )
            return

        logger.info(
            "Processed Discord message %s with outcome=%s reason=%s",
            message.id,
            result.kind.value,
            result.reason or "-",
        )
        if result.kind is OutcomeKind.ANSWERED:
            await message.reply(
                format_answer(result),
                mention_author=False,
                allowed_mentions=self._allowed_mentions,
            )
        elif result.kind is OutcomeKind.ESCALATED:
            await message.reply(
                format_escalation(result),
                mention_author=False,
                allowed_mentions=self._allowed_mentions,
            )
            await self._post_support_ticket(message, result)

    async def _post_support_ticket(
        self,
        message: discord.Message,
        result: ProcessingResult,
    ) -> None:
        channel = await self._get_support_channel()
        ticket = format_support_ticket(
            author_mention=message.author.mention,
            question=message.content,
            source_url=message.jump_url,
            mentor_mention=result.mentor_mention,
            review_id=result.review_id,
            mentor_draft=result.mentor_draft,
        )
        context_id = ""
        if isinstance(channel, discord.ForumChannel):
            created = await channel.create_thread(
                name=_forum_post_title(message.content),
                content=ticket,
                allowed_mentions=self._allowed_mentions,
            )
            thread = getattr(created, "thread", created)
            context_id = str(thread.id)
            logger.info("Created support forum post for message %s", message.id)
        elif hasattr(channel, "send"):
            posted = await channel.send(
                ticket,
                allowed_mentions=self._allowed_mentions,
            )
            context_id = str(posted.id)
            if isinstance(posted, discord.Message):
                try:
                    thread = await posted.create_thread(
                        name=_forum_post_title(message.content),
                    )
                    context_id = str(thread.id)
                except (discord.Forbidden, discord.HTTPException):
                    logger.info(
                        "Could not create review thread; use Review ID commands"
                    )
            logger.info("Posted support ticket for message %s", message.id)
        else:
            raise TypeError("DISCORD_SUPPORT_CHANNEL_ID is not messageable")

        if result.review_id:
            bound = await asyncio.to_thread(
                self._support_workflow.bind_review_context,
                result.review_id,
                context_id,
            )
            if not bound:
                logger.error(
                    "Could not bind review %s to context %s",
                    result.review_id,
                    context_id,
                )

    async def _handle_review_command(
        self,
        message: discord.Message,
        action: ReviewAction,
        edited_answer: str,
        review_id: str,
    ) -> None:
        roles = tuple(
            str(role.id)
            for role in getattr(message.author, "roles", ())
        )
        permissions = getattr(message.author, "guild_permissions", None)
        decision = MentorDecisionInput(
            support_context_id=str(message.channel.id),
            reviewer_id=str(message.author.id),
            reviewer_role_ids=roles,
            can_moderate=bool(
                permissions and permissions.manage_messages
            ),
            action=action,
            edited_answer=edited_answer,
            review_id=review_id,
        )
        result = await asyncio.to_thread(
            self._support_workflow.decide,
            decision,
        )
        if result.kind is not ReviewDecisionKind.READY_TO_SEND:
            await message.reply(
                result.message,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        succeeded = False
        try:
            channel = self.get_channel(int(result.original_channel_id))
            if channel is None:
                channel = await self.fetch_channel(int(result.original_channel_id))
            if not hasattr(channel, "fetch_message"):
                raise TypeError("Original channel does not support messages")
            original = await channel.fetch_message(int(result.original_message_id))
            await original.reply(
                format_approved_answer(result),
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            succeeded = True
        except Exception:
            logger.exception("Failed to deliver approved review %s", result.review_id)
        finally:
            await asyncio.to_thread(
                self._support_workflow.complete_delivery,
                result.review_id,
                succeeded,
            )

        confirmation = (
            f"✅ Đã gửi bản mentor duyệt. Review `{result.review_id}` hoàn tất."
            if succeeded
            else "Không gửi được về tin nhắn gốc; review đã quay lại trạng thái pending."
        )
        await message.reply(
            confirmation,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _digest_worker(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await self._send_digest(force=False)
            except Exception:
                logger.exception("Scheduled digest delivery failed")
            await asyncio.sleep(self._support_workflow.digest_poll_seconds)

    async def _send_digest(
        self,
        *,
        force: bool,
        acknowledgement: discord.Message | None = None,
    ) -> None:
        result = await asyncio.to_thread(
            self._support_workflow.build_digest,
            datetime.now(UTC),
            force=force,
        )
        if result is None:
            if acknowledgement:
                await acknowledgement.reply(
                    "Digest chưa tới giờ hoặc hôm nay đã được gửi.",
                    mention_author=False,
                )
            return

        channel = await self._get_support_channel()
        content = format_digest(result)
        if isinstance(channel, discord.ForumChannel):
            await channel.create_thread(
                name=f"Digest tồn đọng {result.report_date}",
                content=content,
                allowed_mentions=self._allowed_mentions,
            )
        elif hasattr(channel, "send"):
            await channel.send(content, allowed_mentions=self._allowed_mentions)
        else:
            raise TypeError("DISCORD_SUPPORT_CHANNEL_ID is not messageable")

        await asyncio.to_thread(
            self._support_workflow.mark_digest_sent,
            result.report_date,
        )
        if acknowledgement:
            await acknowledgement.reply(
                "✅ Đã tạo digest mới trong kênh hỗ trợ.",
                mention_author=False,
            )

    async def _get_support_channel(self):
        channel = self.get_channel(self._support_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self._support_channel_id)
        return channel

    def _is_support_context(self, channel) -> bool:
        return (
            channel.id == self._support_channel_id
            or getattr(channel, "parent_id", None) == self._support_channel_id
        )


def create_discord_client(
    *,
    engine: RAGEnginePort,
    support_workflow: SupportWorkflowPort,
    monitored_channel_ids: frozenset[int],
    support_channel_id: int,
) -> K3MateDiscordClient:
    return K3MateDiscordClient(
        engine=engine,
        support_workflow=support_workflow,
        monitored_channel_ids=monitored_channel_ids,
        support_channel_id=support_channel_id,
    )


def _forum_post_title(question: str, limit: int = 90) -> str:
    normalized = " ".join(question.split()).strip()
    title = f"Cần hỗ trợ: {normalized}"
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def _parse_review_command(
    content: str,
) -> tuple[ReviewAction, str, str] | None:
    value = content.strip()
    parts = value.split(maxsplit=1)
    command = parts[0] if parts else ""
    payload = parts[1].strip() if len(parts) == 2 else ""
    if command == "!approve":
        review_id = payload
        return ReviewAction.APPROVE, "", review_id
    if command == "!reject":
        review_id = payload
        return ReviewAction.REJECT, "", review_id
    if command == "!send":
        review_id = ""
        if "|" in payload:
            candidate, payload = payload.split("|", maxsplit=1)
            review_id = candidate.strip()
            payload = payload.strip()
        return ReviewAction.EDIT_AND_SEND, payload, review_id
    return None
