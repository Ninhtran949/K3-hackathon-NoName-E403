from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.config import load_settings
from bot.db import QuestionStore
from bot.gemini_client import GeminiEngine
from bot.pipeline import AnswerPipeline
from bot.rag import KnowledgeBase

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("course-bot")


class CourseBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # Cần Message Content Intent (bật ở Developer Portal) để đọc history / tóm tắt / sync.
        intents.message_content = True
        intents.members = False
        super().__init__(command_prefix="!", intents=intents)
        self.settings = load_settings()
        self.kb = KnowledgeBase(self.settings.kb_dir)
        self.engine = GeminiEngine(self.settings.gemini_api_key, self.settings.gemini_model)
        self.pipeline = AnswerPipeline(
            self.kb,
            self.engine,
            top_k=self.settings.top_k,
            similarity_threshold=self.settings.similarity_threshold,
        )
        self.store = QuestionStore(self.settings.sqlite_path)

    async def setup_hook(self) -> None:
        await self.store.init()
        if self.kb.count() == 0:
            n = self.kb.ingest_markdown_dir(self.settings.knowledge_dir)
            log.info("Seeded knowledge base with %s chunks", n)
        self.tree.add_command(ask)
        self.tree.add_command(tomtat)
        self.tree.add_command(pending)
        self.tree.add_command(resolve)
        self.tree.add_command(digest)
        self.tree.add_command(reindex)
        self.tree.add_command(sync_channels)
        try:
            if self.settings.guild_id:
                guild = discord.Object(id=self.settings.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("Synced %s guild commands to %s", len(synced), self.settings.guild_id)
            else:
                synced = await self.tree.sync()
                log.info("Synced %s global commands (có thể mất vài phút mới hiện)", len(synced))
        except discord.Forbidden:
            log.warning(
                "Không sync được slash command (Missing Access). "
                "Kiểm tra bot đã vào server chưa / DISCORD_GUILD_ID. Vẫn chạy @mention."
            )
            try:
                synced = await self.tree.sync()
                log.info("Fallback: synced %s global commands", len(synced))
            except Exception as exc:  # noqa: BLE001
                log.warning("Global sync cũng lỗi: %s", exc)
        self.timeout_watch.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    @tasks.loop(minutes=15)
    async def timeout_watch(self) -> None:
        stale = await self.store.list_stale(self.settings.pending_timeout_hours)
        mention = _mentor_mention()
        if not stale or not mention:
            return
        for row in stale:
            channel = self.get_channel(int(row["channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                continue
            await channel.send(
                f"⏰ Câu hỏi vẫn Pending > {self.settings.pending_timeout_hours}h "
                f"{mention}\n> {row['question'][:300]}"
            )
            await self.store.mark_escalated(row["message_id"])

    @timeout_watch.before_loop
    async def before_timeout_watch(self) -> None:
        await self.wait_until_ready()


bot = CourseBot()


def _allowed_ask_channel(interaction_or_message_channel_id: int) -> bool:
    ask_id = bot.settings.ask_channel_id
    return ask_id is None or ask_id == interaction_or_message_channel_id


def _mentor_mention() -> str | None:
    # Ưu tiên tag đúng 1 người Admin/Mentor, tránh nhầm role → bot khác
    if bot.settings.mentor_user_id:
        return f"<@{bot.settings.mentor_user_id}>"
    if bot.settings.mentor_role_id:
        return f"<@&{bot.settings.mentor_role_id}>"
    return None


async def _handle_question(
    *,
    question: str,
    author_id: int,
    guild_id: int | None,
    channel_id: int,
    message_id: str,
) -> str:
    result = bot.pipeline.ask(question)
    reply = bot.pipeline.format_discord_reply(
        result,
        mentor_mention=_mentor_mention(),
    )
    if not result.decision.grounded:
        await bot.store.add_pending(
            guild_id=str(guild_id) if guild_id else None,
            channel_id=str(channel_id),
            message_id=message_id,
            author_id=str(author_id),
            question=question,
        )
    return reply


@app_commands.command(name="ask", description="Hỏi trợ lý học viên (chỉ trả lời khi có căn cứ)")
@app_commands.describe(question="Câu hỏi của bạn")
async def ask(interaction: discord.Interaction, question: str) -> None:
    if not _allowed_ask_channel(interaction.channel_id or 0):
        await interaction.response.send_message(
            "Lệnh /ask chỉ dùng trong kênh hỏi đáp được cấu hình.",
            ephemeral=True,
        )
        return
    await interaction.response.defer(thinking=True)
    try:
        reply = await _handle_question(
            question=question,
            author_id=interaction.user.id,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id or 0,
            message_id=f"interaction:{interaction.id}",
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("ask failed")
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            reply = (
                "Gemini đang hết quota/rate-limit. "
                "Đợi vài phút hoặc đổi `GEMINI_MODEL` / tạo API key mới rồi restart bot."
            )
        else:
            reply = f"Lỗi khi gọi AI: `{type(exc).__name__}`. Xem log terminal để biết chi tiết."
    await interaction.followup.send(reply)


@app_commands.command(
    name="tomtat",
    description="Tóm tắt hội thoại gần đây trong kênh hiện tại (không dùng FAQ)",
)
@app_commands.describe(
    so_tin="Số tin nhắn gần nhất để tóm tắt (mặc định 30, tối đa 100)",
    focus="(Tuỳ chọn) muốn nhấn mạnh gì, ví dụ: việc cần làm",
)
async def tomtat(
    interaction: discord.Interaction,
    so_tin: app_commands.Range[int, 5, 100] = 30,
    focus: str = "",
) -> None:
    channel = interaction.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        await interaction.response.send_message(
            "Chỉ dùng /tomtat trong kênh text hoặc thread.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)
    lines: list[str] = []
    async for message in channel.history(limit=int(so_tin)):
        text = (message.content or "").strip()
        if not text:
            continue
        author = message.author.display_name
        lines.append(f"{author}: {text}")

    if not lines:
        await interaction.followup.send(
            "Không đọc được nội dung tin nhắn. "
            "Hãy bật **Message Content Intent** trong Developer Portal rồi restart bot."
        )
        return

    transcript = "\n".join(reversed(lines))
    try:
        summary = bot.engine.summarize_chat(transcript, focus=focus)
    except Exception as exc:  # noqa: BLE001
        log.exception("tomtat failed")
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            summary = "Gemini đang hết quota/rate-limit. Đợi vài phút rồi thử lại."
        else:
            summary = f"Lỗi khi tóm tắt: `{type(exc).__name__}`."

    header = f"**Tóm tắt {len(lines)} tin gần nhất trong #{getattr(channel, 'name', 'channel')}:**\n"
    body = header + summary
    if len(body) > 1900:
        body = body[:1900] + "\n…"
    await interaction.followup.send(body)


@app_commands.command(
    name="pending",
    description="Xem danh sách câu hỏi đang chờ Mentor (Pending/Escalated)",
)
@app_commands.describe(limit="Số câu tối đa (mặc định 10)")
async def pending(
    interaction: discord.Interaction,
    limit: app_commands.Range[int, 1, 25] = 10,
) -> None:
    rows = await bot.store.list_open(limit=int(limit))
    counts = await bot.store.count_by_status()
    if not rows:
        await interaction.response.send_message(
            "Không có câu hỏi Pending/Escalated.",
            ephemeral=True,
        )
        return
    lines = [
        f"**Hàng đợi hỗ trợ** — Pending={counts.get('Pending', 0)}, "
        f"Escalated={counts.get('Escalated', 0)}, Resolved={counts.get('Resolved', 0)}",
        "",
    ]
    for row in rows:
        q = (row["question"] or "").replace("\n", " ")
        if len(q) > 120:
            q = q[:120] + "…"
        lines.append(
            f"- `#{row['id']}` [{row['status']}] <@{row['author_id']}>: {q}"
        )
    lines.append("\nMentor dùng `/resolve id:...` sau khi trả lời xong.")
    body = "\n".join(lines)
    if len(body) > 1900:
        body = body[:1900] + "\n…"
    await interaction.response.send_message(body, ephemeral=True)


@app_commands.command(
    name="resolve",
    description="Đánh dấu câu hỏi Pending đã được Mentor trả lời",
)
@app_commands.describe(
    id="ID trong /pending (ưu tiên)",
    author="Hoặc chọn học viên — sẽ resolve câu mới nhất của họ",
)
async def resolve(
    interaction: discord.Interaction,
    id: int | None = None,
    author: discord.Member | None = None,
) -> None:
    if not interaction.user.guild_permissions.manage_messages:  # type: ignore[union-attr]
        # Cho phép mentor role / mentor user nếu không có Manage Messages
        is_mentor = False
        if bot.settings.mentor_user_id and interaction.user.id == bot.settings.mentor_user_id:
            is_mentor = True
        if bot.settings.mentor_role_id and isinstance(interaction.user, discord.Member):
            if any(r.id == bot.settings.mentor_role_id for r in interaction.user.roles):
                is_mentor = True
        if not is_mentor:
            await interaction.response.send_message(
                "Chỉ Mentor/Admin mới resolve được.",
                ephemeral=True,
            )
            return

    if id is not None:
        match = await bot.store.mark_resolved_by_id(int(id))
        if match is None:
            await interaction.response.send_message(
                f"Không thấy câu `#{id}`.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Đã resolve `#{id}`: {(match['question'] or '')[:160]}",
            ephemeral=True,
        )
        return

    if author is not None:
        row = await bot.store.resolve_latest_for_author(str(author.id))
        if not row:
            await interaction.response.send_message(
                f"{author.mention} không có câu Pending/Escalated.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Đã resolve `#{row['id']}` của {author.mention}: {(row['question'] or '')[:160]}",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        "Cần truyền `id` (từ /pending) hoặc `author`.",
        ephemeral=True,
    )


@app_commands.command(
    name="digest",
    description="Tóm tắt hàng đợi Pending cho Mentor (Signal Layer)",
)
async def digest(interaction: discord.Interaction) -> None:
    rows = await bot.store.list_open(limit=30)
    counts = await bot.store.count_by_status()
    if not rows:
        await interaction.response.send_message(
            "Hàng đợi trống — không có gì để digest.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)
    bullets = []
    for row in rows[:20]:
        q = (row["question"] or "").replace("\n", " ")
        if len(q) > 140:
            q = q[:140] + "…"
        bullets.append(f"- [{row['status']}] {q}")
    transcript = "\n".join(bullets)
    try:
        summary = bot.engine.summarize_chat(
            transcript,
            focus=(
                "Đây là hàng đợi câu hỏi Pending/Escalated trên Discord. "
                "Tóm tắt theo nhóm chủ đề, nêu câu nào cần ưu tiên (deadline/điểm/link), "
                "và gợi ý Mentor làm gì tiếp."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("digest failed")
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            summary = "Gemini đang hết quota/rate-limit. Đợi vài phút rồi thử lại."
        else:
            summary = f"Lỗi khi tạo digest: `{type(exc).__name__}`."

    header = (
        f"**Digest hàng đợi** — Pending={counts.get('Pending', 0)}, "
        f"Escalated={counts.get('Escalated', 0)}, Resolved={counts.get('Resolved', 0)}\n\n"
    )
    body = header + summary
    if len(body) > 1900:
        body = body[:1900] + "\n…"
    mention = _mentor_mention()
    if mention:
        body = f"{mention}\n{body}"
    await interaction.followup.send(body)


@app_commands.command(name="reindex", description="Index lại file trong knowledge/ (admin)")
async def reindex(interaction: discord.Interaction) -> None:
    if not interaction.user.guild_permissions.manage_guild:  # type: ignore[union-attr]
        await interaction.response.send_message("Cần quyền Manage Server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    bot.kb.reset()
    n = bot.kb.ingest_markdown_dir(bot.settings.knowledge_dir)
    await interaction.followup.send(f"Đã reindex {n} chunks từ knowledge/.", ephemeral=True)


@app_commands.command(
    name="sync_channels",
    description="Đọc lịch sử các kênh kiến thức đã cấu hình và nạp vào RAG",
)
@app_commands.describe(limit="Số tin nhắn tối đa mỗi kênh (mặc định 200)")
async def sync_channels(interaction: discord.Interaction, limit: int = 200) -> None:
    if not interaction.user.guild_permissions.manage_guild:  # type: ignore[union-attr]
        await interaction.response.send_message("Cần quyền Manage Server.", ephemeral=True)
        return
    if not bot.settings.knowledge_channel_ids:
        await interaction.response.send_message(
            "Chưa cấu hình KNOWLEDGE_CHANNEL_IDS trong .env",
            ephemeral=True,
        )
        return
    await interaction.response.defer(ephemeral=True)
    total = 0
    for channel_id in bot.settings.knowledge_channel_ids:
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.HTTPException:
                continue
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            continue
        async for message in channel.history(limit=max(1, min(limit, 1000))):
            if message.author.bot or not message.content.strip():
                continue
            total += bot.kb.upsert_message(
                message_id=str(message.id),
                content=message.content,
                channel_name=getattr(channel, "name", str(channel.id)),
                jump_url=message.jump_url,
            )
    await interaction.followup.send(
        f"Đã nạp/ cập nhật khoảng {total} chunks từ kênh kiến thức.",
        ephemeral=True,
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or not bot.user:
        return
    await bot.process_commands(message)

    mentioned = bot.user in message.mentions
    if not mentioned:
        return
    if not _allowed_ask_channel(message.channel.id):
        return

    question = message.content
    for mention in message.mentions:
        question = question.replace(f"<@{mention.id}>", "")
        question = question.replace(f"<@!{mention.id}>", "")
    question = question.strip()
    if not question:
        await message.reply("Bạn hỏi gì nào? Ví dụ: `@bot deadline nộp bài khi nào?`")
        return

    async with message.channel.typing():
        try:
            reply = await _handle_question(
                question=question,
                author_id=message.author.id,
                guild_id=message.guild.id if message.guild else None,
                channel_id=message.channel.id,
                message_id=str(message.id),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("mention ask failed")
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                reply = "Gemini đang hết quota/rate-limit. Đợi vài phút rồi thử lại."
            else:
                reply = f"Lỗi khi gọi AI: `{type(exc).__name__}`."
    await message.reply(reply)


def main() -> None:
    settings = load_settings()
    if not settings.discord_token:
        raise RuntimeError("Thiếu DISCORD_BOT_TOKEN trong codebase/.env")
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
