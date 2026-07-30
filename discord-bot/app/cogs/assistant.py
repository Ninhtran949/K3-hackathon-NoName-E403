from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands, tasks

from app.ai import AnthropicAnswerGenerator
from app.config import Settings
from app.database import Database, SupportCase
from app.ingest import MessageIngestor
from app.models import KnowledgeSource
from app.qa import QAPipeline, QAResult
from app.retrieval import RetrievalService
from app.routing import RouteDecision, RoutingConfig, decide_route, load_routing_config
from app.safety import contains_likely_secret

logger = logging.getLogger(__name__)

SUPPORT_STATUS_LABELS = {
    "pending": "⏳ Chưa xử lý",
    "viewing": "👀 Đang xem",
    "resolved": "✅ Đã xử lý",
}
_MENTION_COOLDOWN_SECONDS = 10.0
_QUESTION_MIN_LENGTH = 5
_QUESTION_MAX_LENGTH = 1_500


@dataclass(frozen=True, slots=True)
class LiveSource:
    source: KnowledgeSource
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class SupportOutcome:
    logged: bool
    channel: discord.TextChannel | None
    role: discord.Role | None
    detail: str
    role_pinged: bool = False


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


def _numeric_role_id(value: str | int | None) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    normalized = value.strip()
    return int(normalized) if normalized.isdigit() and int(normalized) > 0 else None


class AssistantCog(commands.Cog):
    """Grounded Build Phase Q&A, source ingest, and human escalation."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings = cast(Settings, bot.settings)
        self.database = cast(Database, bot.database)
        self.ingestor = MessageIngestor(self.database, self.settings)
        self.retrieval = RetrievalService(
            top_k=self.settings.top_k,
            threshold=self.settings.similarity_threshold,
        )
        generator = (
            AnthropicAnswerGenerator(
                api_key=self.settings.anthropic_api_key,
                model=self.settings.anthropic_model,
            )
            if self.settings.anthropic_api_key
            else None
        )
        self.qa = QAPipeline(
            retriever=self.retrieval,
            answer_generator=generator,
            similarity_threshold=self.settings.similarity_threshold,
            top_k=self.settings.top_k,
        )
        self.routing = self._load_routing()
        self._mention_last_used: dict[int, float] = {}

    def _load_routing(self) -> RoutingConfig:
        try:
            return load_routing_config(self.settings.routing_path)
        except ValueError:
            logger.exception(
                "Không thể nạp routing config; dùng role hỗ trợ mặc định",
                extra={"routing_path": str(self.settings.routing_path)},
            )
            return RoutingConfig(
                routes=(),
                default_role_id=self.settings.default_support_role_id,
            )

    @app_commands.command(
        name="ask",
        description="Hỏi bot về thông tin Build Phase từ các nguồn đã được cho phép",
    )
    @app_commands.describe(question="Câu hỏi cần bot tra cứu")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(2, 10.0, key=lambda item: (item.guild_id, item.user.id))
    async def ask(
        self,
        interaction: discord.Interaction,
        question: app_commands.Range[str, _QUESTION_MIN_LENGTH, _QUESTION_MAX_LENGTH],
    ) -> None:
        guild = interaction.guild
        member = interaction.user
        channel = interaction.channel
        if (
            guild is None
            or not isinstance(member, discord.Member)
            or not isinstance(channel, (discord.TextChannel, discord.Thread))
        ):
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong kênh chữ của server.",
                ephemeral=True,
            )
            return
        if isinstance(channel, discord.Thread) and channel.is_private():
            await interaction.response.send_message(
                "P0 không xử lý câu hỏi trong private thread để tránh lộ nội dung.",
                ephemeral=True,
            )
            return

        if channel.id not in self.settings.qa_channel_ids:
            detail = (
                "DISCORD_QA_CHANNEL_IDS chưa được cấu hình."
                if not self.settings.qa_channel_ids
                else "Hãy dùng lệnh trong một kênh Q&A đã được cấu hình."
            )
            await interaction.response.send_message(detail, ephemeral=True)
            return
        if contains_likely_secret(question):
            await interaction.response.send_message(
                "Câu hỏi có vẻ chứa API key, token hoặc mật khẩu nên mình không xử lý. "
                "Hãy xóa/đổi credential đó rồi gửi lại câu hỏi không kèm bí mật.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=self.settings.ask_ephemeral, thinking=True)
        result = await self._answer(question, guild, member)

        if result.status == "answered":
            live_sources = await self._validate_live_sources(
                guild,
                member,
                result.cited_sources,
            )
            if len(live_sources) == len(result.cited_sources):
                await interaction.followup.send(
                    embed=self._answer_embed(result.answer or "", live_sources),
                    ephemeral=self.settings.ask_ephemeral,
                )
                return
            reason_override = "Nguồn vừa thay đổi, bị xóa hoặc không còn truy cập được."
        else:
            reason_override = None

        outcome = await self._route_support(
            guild=guild,
            requester=member,
            origin_channel=channel,
            origin_message=None,
            request_key=f"interaction:{guild.id}:{interaction.id}",
            question=question,
            result=result,
            reason_override=reason_override,
        )
        await interaction.followup.send(
            self._support_user_message(outcome, result, reason_override),
            ephemeral=self.settings.ask_ephemeral,
        )

    @app_commands.command(
        name="help",
        description="Xem cách dùng trợ lý Build Phase",
    )
    async def assistant_help(self, interaction: discord.Interaction) -> None:
        source_ready = bool(
            self.settings.enable_message_content_intent
            and (self.settings.qa_channel_ids or self.settings.announcement_channel_ids)
        )
        support_ready = bool(
            self.settings.support_channel_id
            and (
                self.settings.default_support_role_id
                or self.settings.mentor_role_ids
                or self.settings.admin_role_ids
            )
        )
        embed = discord.Embed(
            title="Trợ lý Build Phase",
            description=(
                "Dùng `/ask question:...` hoặc mention bot kèm câu hỏi. "
                "Bot chỉ trả lời khi tìm thấy nguồn đủ mạnh và kiểm tra được link gốc."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Khi chưa chắc chắn",
            value=(
                "Bot không đoán deadline, điểm số hoặc quy định. Câu hỏi sẽ được "
                "chuyển sang kênh hỗ trợ để mentor/admin xử lý."
            ),
            inline=False,
        )
        embed.add_field(
            name="Trạng thái hệ thống",
            value=(
                f"Nguồn cho phép: {'✅' if source_ready else '⚠️ chưa cấu hình'}\n"
                f"AI: {'✅' if self.settings.anthropic_api_key else '⚠️ chưa cấu hình'}\n"
                f"Hỗ trợ người thật: {'✅' if support_ready else '⚠️ chưa cấu hình'}"
            ),
            inline=False,
        )
        embed.set_footer(text="Câu trả lời mặc định chỉ hiển thị cho người gọi lệnh.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-reindex",
        description="Nạp lại các tin gần nhất từ allowlist vào kho nguồn",
    )
    @app_commands.describe(
        channel="Một kênh cụ thể; để trống để nạp tất cả kênh allowlist",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def admin_reindex(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = interaction.guild
        member = interaction.user
        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.",
                ephemeral=True,
            )
            return
        if not self.settings.enable_message_content_intent:
            await interaction.response.send_message(
                "Reindex đang tắt vì ENABLE_MESSAGE_CONTENT_INTENT=false. "
                "Hãy bật cả trong `.env` và Discord Developer Portal trước.",
                ephemeral=True,
            )
            return

        requested_ids = self.ingestor.allowed_channel_ids
        if channel is not None:
            if channel.id not in requested_ids:
                await interaction.response.send_message(
                    "Kênh này không nằm trong allowlist Q&A/announcement.",
                    ephemeral=True,
                )
                return
            requested_ids = frozenset({channel.id})
        if not requested_ids:
            await interaction.response.send_message(
                "Chưa có kênh nào trong DISCORD_QA_CHANNEL_IDS hoặc "
                "DISCORD_ANNOUNCEMENT_CHANNEL_IDS.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        accepted = 0
        skipped = 0
        failed_channels: list[str] = []
        remaining = self.settings.max_reindex_messages
        for channel_id in sorted(requested_ids):
            if remaining <= 0:
                break
            source_channel = guild.get_channel(channel_id)
            if not isinstance(source_channel, discord.TextChannel):
                failed_channels.append(str(channel_id))
                continue
            bot_member = guild.me
            if bot_member is None:
                failed_channels.append(source_channel.mention)
                continue
            permissions = source_channel.permissions_for(bot_member)
            if not (permissions.view_channel and permissions.read_message_history):
                failed_channels.append(source_channel.mention)
                continue

            try:
                async for message in source_channel.history(limit=remaining):
                    remaining -= 1
                    ingest_result = await self.ingestor.ingest_message(message)
                    if ingest_result.accepted:
                        accepted += 1
                    else:
                        skipped += 1
            except (discord.Forbidden, discord.HTTPException):
                failed_channels.append(source_channel.mention)

        failed_text = (
            f"\nKênh lỗi/thiếu quyền: {', '.join(failed_channels)}" if failed_channels else ""
        )
        await interaction.followup.send(
            f"Reindex hoàn tất: **{accepted}** nguồn được lưu/cập nhật, "
            f"**{skipped}** tin bị bỏ qua.{failed_text}",
            ephemeral=True,
        )

    @app_commands.command(
        name="admin-test-route",
        description="Kiểm tra một câu hỏi sẽ được route tới nhóm nào",
    )
    @app_commands.describe(question="Câu hỏi dùng để thử routing")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def admin_test_route(
        self,
        interaction: discord.Interaction,
        question: app_commands.Range[str, _QUESTION_MIN_LENGTH, _QUESTION_MAX_LENGTH],
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.",
                ephemeral=True,
            )
            return
        decision = decide_route(question, self.routing)
        role = self._resolve_support_role(guild, decision, force_admin=False)
        matched = ", ".join(decision.matched_keywords) or "không có"
        destination = role.mention if role else "chưa có role ID hợp lệ"
        await interaction.response.send_message(
            f"Route: **{decision.route_name or 'mặc định'}**\n"
            f"Keyword: {matched}\n"
            f"Điểm: {decision.score}\n"
            f"Đích thực tế: {destination}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _answer(
        self,
        question: str,
        guild: discord.Guild,
        member: discord.Member,
        *,
        channel_ids: frozenset[int] | None = None,
        excluded_message_id: int | None = None,
    ) -> QAResult:
        visible_channel_ids = self._visible_channel_ids(
            guild,
            member,
            channel_ids=channel_ids,
        )
        sources = await asyncio.to_thread(
            self.database.list_knowledge_sources,
            guild.id,
            allowed_channel_ids=visible_channel_ids,
        )
        # P0 accepts only live Discord sources. Static documents require a
        # separate explicit trust allowlist before they may be exposed.
        authorized_sources = [
            source
            for source in sources
            if source.source_type == "discord_message"
            and source.channel_id in visible_channel_ids
            and source.message_id != excluded_message_id
        ]
        return await self.qa.answer(question, authorized_sources)

    async def cog_load(self) -> None:
        self.cleanup_expired_sources.start()

    async def cog_unload(self) -> None:
        self.cleanup_expired_sources.cancel()

    @tasks.loop(hours=24)
    async def cleanup_expired_sources(self) -> None:
        deleted = await asyncio.to_thread(
            self.database.cleanup_expired_sources,
            self.settings.source_retention_days,
        )
        if deleted:
            logger.info("Đã xóa %s nguồn community quá hạn", deleted)
        deleted_cases = await asyncio.to_thread(
            self.database.cleanup_expired_support_cases,
            self.settings.support_case_retention_days,
        )
        if deleted_cases:
            logger.info("Đã xóa %s support case đã xử lý quá hạn", deleted_cases)

    @cleanup_expired_sources.before_loop
    async def before_cleanup_expired_sources(self) -> None:
        await self.bot.wait_until_ready()

    def _visible_channel_ids(
        self,
        guild: discord.Guild,
        member: discord.Member,
        *,
        channel_ids: frozenset[int] | None = None,
    ) -> frozenset[int]:
        requested = self.ingestor.allowed_channel_ids
        if channel_ids is not None:
            requested &= channel_ids

        visible: set[int] = set()
        for channel_id in requested:
            channel = guild.get_channel_or_thread(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue
            if isinstance(channel, discord.Thread) and channel.is_private():
                continue
            permissions = channel.permissions_for(member)
            if permissions.view_channel and permissions.read_message_history:
                visible.add(channel_id)
        return frozenset(visible)

    async def _validate_live_sources(
        self,
        guild: discord.Guild,
        member: discord.Member,
        sources: tuple[KnowledgeSource, ...],
    ) -> tuple[LiveSource, ...]:
        validated: list[LiveSource] = []
        for source in sources:
            if (
                source.source_type != "discord_message"
                or source.guild_id != guild.id
                or source.channel_id is None
                or source.message_id is None
                or source.channel_id not in self.ingestor.allowed_channel_ids
            ):
                continue

            channel = guild.get_channel_or_thread(source.channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue
            if isinstance(channel, discord.Thread) and channel.is_private():
                continue
            permissions = channel.permissions_for(member)
            if not (permissions.view_channel and permissions.read_message_history):
                continue

            try:
                message = await channel.fetch_message(source.message_id)
            except discord.NotFound:
                await self.ingestor.delete_message(
                    guild.id,
                    source.channel_id,
                    source.message_id,
                )
                continue
            except (discord.Forbidden, discord.HTTPException):
                continue

            if message.content.strip() != source.content.strip():
                # Keep the index current, but never send an answer produced from
                # stale text. A later request may use the refreshed source.
                await self.ingestor.ingest_message(message)
                continue

            channel_name = discord.utils.escape_markdown(getattr(channel, "name", str(channel.id)))
            validated.append(
                LiveSource(
                    source=source,
                    label=f"#{_truncate(channel_name, 60)}",
                    url=message.jump_url,
                )
            )
        return tuple(validated)

    def _answer_embed(
        self,
        answer: str,
        sources: tuple[LiveSource, ...],
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Câu trả lời từ nguồn đã xác minh",
            description=_truncate(answer, 4_000),
            color=discord.Color.green(),
        )
        source_lines = [
            f"{index}. [{source.label}]({source.url})"
            for index, source in enumerate(sources, start=1)
        ]
        embed.add_field(
            name="Nguồn",
            value=_truncate("\n".join(source_lines), 1_024),
            inline=False,
        )
        embed.set_footer(text="Nguồn được kiểm tra lại ngay trước khi gửi; bot không tự tạo link.")
        return embed

    async def _route_support(
        self,
        *,
        guild: discord.Guild,
        requester: discord.Member,
        origin_channel: discord.TextChannel | discord.Thread,
        origin_message: discord.Message | None,
        request_key: str,
        question: str,
        result: QAResult,
        reason_override: str | None = None,
    ) -> SupportOutcome:
        decision = decide_route(f"{question} {result.topic}".strip(), self.routing)
        role = self._resolve_support_role(
            guild,
            decision,
            force_admin=result.status == "conflict",
        )
        support_channel = (
            guild.get_channel(self.settings.support_channel_id)
            if self.settings.support_channel_id
            else None
        )
        if not isinstance(support_channel, discord.TextChannel):
            return SupportOutcome(
                False,
                None,
                role,
                "Thiếu hoặc sai DISCORD_SUPPORT_CHANNEL_ID.",
            )

        bot_member = guild.me
        if bot_member is None:
            return SupportOutcome(False, support_channel, role, "Bot chưa sẵn sàng.")
        permissions = support_channel.permissions_for(bot_member)
        if not (permissions.view_channel and permissions.send_messages):
            return SupportOutcome(
                False,
                support_channel,
                role,
                "Bot thiếu quyền View Channel hoặc Send Messages tại kênh hỗ trợ.",
            )
        role_pingable = bool(role and (role.mentionable or permissions.mention_everyone))

        case = await asyncio.to_thread(
            self.database.create_support_case,
            request_key=request_key,
            guild_id=guild.id,
            requester_id=requester.id,
            origin_channel_id=origin_channel.id,
            origin_message_id=origin_message.id if origin_message else None,
            question=question,
            topic=result.topic,
            routed_role_id=role.id if role else None,
        )
        if case.support_message_id is not None:
            return SupportOutcome(
                True,
                support_channel,
                role,
                "Đã tồn tại yêu cầu hỗ trợ.",
                role_pinged=role_pingable,
            )

        embed = self._support_embed(
            case,
            requester=requester,
            origin_channel=origin_channel,
            origin_message=origin_message,
            result=result,
            route_decision=decision,
            role=role,
            reason_override=reason_override,
        )
        allowed_mentions = discord.AllowedMentions(
            everyone=False,
            users=False,
            roles=[role] if role_pingable and role else False,
            replied_user=False,
        )
        try:
            support_message = await support_channel.send(
                content=role.mention if role_pingable and role else None,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
        except (discord.Forbidden, discord.HTTPException):
            logger.exception(
                "Không thể đăng yêu cầu hỗ trợ",
                extra={"support_channel_id": support_channel.id, "case_id": case.id},
            )
            return SupportOutcome(
                False,
                support_channel,
                role,
                "Discord từ chối gửi tin vào kênh hỗ trợ.",
            )

        await asyncio.to_thread(
            self.database.attach_support_message,
            case.id,
            support_message.id,
        )
        for emoji in ("👀", "✅"):
            try:
                await support_message.add_reaction(emoji)
            except (discord.Forbidden, discord.HTTPException):
                logger.warning(
                    "Không thể thêm reaction trạng thái",
                    extra={"message_id": support_message.id, "emoji": emoji},
                )

        detail = (
            "Đã tạo yêu cầu hỗ trợ và tag role."
            if role_pingable
            else "Đã tạo yêu cầu nhưng role chưa mentionable hoặc bot thiếu quyền tag role."
        )
        return SupportOutcome(
            True,
            support_channel,
            role,
            detail,
            role_pinged=role_pingable,
        )

    def _resolve_support_role(
        self,
        guild: discord.Guild,
        decision: RouteDecision,
        *,
        force_admin: bool,
    ) -> discord.Role | None:
        if force_admin:
            candidate_ids = sorted(self.settings.admin_role_ids)
        else:
            route_role_id = _numeric_role_id(decision.role_id)
            candidate_ids = [route_role_id] if route_role_id else []
            if self.settings.default_support_role_id not in candidate_ids:
                candidate_ids.append(self.settings.default_support_role_id)

        allowed_ids = self.settings.admin_role_ids | self.settings.mentor_role_ids
        if self.settings.default_support_role_id:
            allowed_ids |= frozenset({self.settings.default_support_role_id})

        for role_id in candidate_ids:
            if role_id is None or role_id not in allowed_ids:
                continue
            role = guild.get_role(role_id)
            if role is not None:
                return role
        return None

    def _support_embed(
        self,
        case: SupportCase,
        *,
        requester: discord.Member,
        origin_channel: discord.TextChannel | discord.Thread,
        origin_message: discord.Message | None,
        result: QAResult,
        route_decision: RouteDecision,
        role: discord.Role | None,
        reason_override: str | None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="❓ Câu hỏi cần hỗ trợ",
            description=_truncate(case.question, 3_500),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Người hỏi",
            value=f"{requester.mention} (`{requester.id}`)",
            inline=True,
        )
        embed.add_field(name="Channel", value=origin_channel.mention, inline=True)
        embed.add_field(
            name="Đã route",
            value=role.mention if role else "Chưa cấu hình role hợp lệ",
            inline=True,
        )
        embed.add_field(
            name="Chủ đề",
            value=_truncate(result.topic or route_decision.route_name or "chưa xác định", 1_024),
            inline=True,
        )
        embed.add_field(
            name="Lý do chuyển",
            value=_truncate(reason_override or result.reason, 1_024),
            inline=False,
        )
        if origin_message is not None:
            embed.add_field(
                name="Tin nhắn gốc",
                value=f"[Mở tin nhắn]({origin_message.jump_url})",
                inline=False,
            )
        embed.add_field(
            name="Trạng thái",
            value=SUPPORT_STATUS_LABELS["pending"],
            inline=False,
        )
        embed.set_footer(text=f"Support case #{case.id}")
        return embed

    def _support_user_message(
        self,
        outcome: SupportOutcome,
        result: QAResult,
        reason_override: str | None,
    ) -> str:
        reason = reason_override or result.reason
        if outcome.logged and outcome.channel is not None:
            if outcome.role_pinged and outcome.role:
                role_text = f" và đã tag **{outcome.role.name}**"
            elif outcome.role:
                role_text = f" cho **{outcome.role.name}**, nhưng role chưa cho phép bot mention"
            else:
                role_text = ", nhưng chưa có role đích hợp lệ"
            return (
                "Mình chưa có đủ thông tin chắc chắn để trả lời. "
                f"Đã ghi câu hỏi vào {outcome.channel.mention}{role_text}.\n"
                f"Lý do: {_truncate(reason, 500)}"
            )
        return (
            "Mình chưa có đủ thông tin chắc chắn để trả lời và chưa thể tạo yêu cầu "
            f"hỗ trợ.\nLý do: {_truncate(reason, 400)}\nCấu hình: {outcome.detail}"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        if self.settings.guild_id and message.guild.id != self.settings.guild_id:
            return

        is_mention = self.bot.user is not None and self.bot.user in message.mentions
        is_qa_question = (
            message.channel.id in self.settings.qa_channel_ids
            and message.content.rstrip().endswith(("?", "？"))
        )
        is_question_request = (
            not message.author.bot
            and message.channel.id in self.settings.qa_channel_ids
            and (is_mention or is_qa_question)
        )
        if is_question_request:
            # A question is input, never evidence. Also remove a stale row if a
            # previously indexed message was edited into a bot question.
            await self.ingestor.delete_message(
                message.guild.id,
                message.channel.id,
                message.id,
            )
        else:
            await self.ingestor.ingest_message(message)

        if (
            message.author.bot
            or self.bot.user is None
            or message.channel.id not in self.settings.qa_channel_ids
            or not (is_mention or is_qa_question)
            or not isinstance(message.author, discord.Member)
            or not isinstance(message.channel, (discord.TextChannel, discord.Thread))
            or (isinstance(message.channel, discord.Thread) and message.channel.is_private())
        ):
            return

        question = message.content
        if is_mention:
            question = re.sub(
                rf"<@!?{self.bot.user.id}>",
                "",
                question,
            )
        question = question.strip()
        if contains_likely_secret(question):
            await message.reply(
                "Tin nhắn có vẻ chứa API key, token hoặc mật khẩu nên mình không lưu hay "
                "chuyển tiếp nội dung này. Bạn nên đổi credential rồi hỏi lại không kèm bí mật.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        if not _QUESTION_MIN_LENGTH <= len(question) <= _QUESTION_MAX_LENGTH:
            await message.reply(
                "Bạn hãy mention mình kèm câu hỏi dài từ 5 đến 1.500 ký tự.",
                mention_author=False,
            )
            return

        now = time.monotonic()
        previous = self._mention_last_used.get(message.author.id, 0.0)
        if now - previous < _MENTION_COOLDOWN_SECONDS:
            return
        self._mention_last_used[message.author.id] = now

        public_channel_ids = self._public_source_channel_ids(message)
        async with message.channel.typing():
            result = await self._answer(
                question,
                message.guild,
                message.author,
                channel_ids=public_channel_ids,
                excluded_message_id=message.id,
            )
            if result.status == "answered":
                live_sources = await self._validate_live_sources(
                    message.guild,
                    message.author,
                    result.cited_sources,
                )
                if len(live_sources) == len(result.cited_sources):
                    await message.reply(
                        embed=self._answer_embed(result.answer or "", live_sources),
                        mention_author=False,
                    )
                    return
                reason_override = "Nguồn vừa thay đổi, bị xóa hoặc không còn truy cập được."
            else:
                reason_override = None

            outcome = await self._route_support(
                guild=message.guild,
                requester=message.author,
                origin_channel=message.channel,
                origin_message=message,
                request_key=f"message:{message.guild.id}:{message.id}",
                question=question,
                result=result,
                reason_override=reason_override,
            )
            await message.reply(
                self._support_user_message(outcome, result, reason_override),
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    def _public_source_channel_ids(self, message: discord.Message) -> frozenset[int]:
        guild = message.guild
        if guild is None:
            return frozenset()

        allowed: set[int] = set()
        if message.channel.id in self.ingestor.allowed_channel_ids:
            allowed.add(message.channel.id)
        for channel_id in self.settings.announcement_channel_ids:
            channel = guild.get_channel_or_thread(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue
            if isinstance(channel, discord.Thread) and channel.is_private():
                continue
            if channel.permissions_for(guild.default_role).view_channel:
                allowed.add(channel_id)
        return frozenset(allowed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        if payload.guild_id is None:
            return
        if self.settings.guild_id and payload.guild_id != self.settings.guild_id:
            return
        if payload.channel_id not in self.ingestor.allowed_channel_ids:
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel_or_thread(payload.channel_id) if guild else None
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return
        if isinstance(channel, discord.Thread) and channel.is_private():
            await self.ingestor.delete_message(
                payload.guild_id,
                payload.channel_id,
                payload.message_id,
            )
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            await self.ingestor.delete_message(
                payload.guild_id,
                payload.channel_id,
                payload.message_id,
            )
            return
        except (discord.Forbidden, discord.HTTPException):
            return

        result = await self.ingestor.ingest_message(message)
        if not result.accepted:
            await self.ingestor.delete_message(
                payload.guild_id,
                payload.channel_id,
                payload.message_id,
            )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.guild_id is None:
            return
        if self.settings.guild_id and payload.guild_id != self.settings.guild_id:
            return
        await self.ingestor.delete_message(
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None:
            return
        if self.settings.guild_id and payload.guild_id != self.settings.guild_id:
            return
        if payload.channel_id not in self.ingestor.allowed_channel_ids:
            return
        await asyncio.gather(
            *(
                self.ingestor.delete_message(
                    payload.guild_id,
                    payload.channel_id,
                    message_id,
                )
                for message_id in payload.message_ids
            )
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        if (
            payload.guild_id is None
            or payload.channel_id != self.settings.support_channel_id
            or str(payload.emoji) not in {"👀", "✅"}
            or (self.bot.user is not None and payload.user_id == self.bot.user.id)
        ):
            return

        case = await asyncio.to_thread(
            self.database.get_support_case_by_message,
            payload.message_id,
        )
        if case is None or case.status == "resolved":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        role_ids = {role.id for role in member.roles}
        authorized_role_ids = self.settings.admin_role_ids | self.settings.mentor_role_ids
        if self.settings.default_support_role_id:
            authorized_role_ids |= frozenset({self.settings.default_support_role_id})
        if not role_ids & authorized_role_ids:
            return

        status = "viewing" if str(payload.emoji) == "👀" else "resolved"
        updated = await asyncio.to_thread(
            self.database.update_support_status,
            payload.message_id,
            status,
        )
        if updated is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            support_message = await channel.fetch_message(payload.message_id)
            if not support_message.embeds:
                return
            embed = discord.Embed.from_dict(support_message.embeds[0].to_dict())
            for index, field in enumerate(embed.fields):
                if field.name == "Trạng thái":
                    embed.set_field_at(
                        index,
                        name="Trạng thái",
                        value=SUPPORT_STATUS_LABELS[status],
                        inline=False,
                    )
                    break
            await support_message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning(
                "Đã cập nhật DB nhưng không thể cập nhật support embed",
                extra={"message_id": payload.message_id, "status": status},
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AssistantCog(bot))
