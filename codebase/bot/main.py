from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.config import load_settings
from bot.db import QuestionStore
from bot.gemini_client import GeminiEngine
from bot.pipeline import (
    AnswerPipeline,
    parse_mention_ids,
    parse_plain_ats,
    _is_user_message_lookup,
)
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
        removed = self.kb.purge_non_channel_sources()
        if removed:
            log.info("Purged %s file-based KB chunks (md/txt/code). Channels only.", removed)
        log.info("KB channel chunks: %s — dùng /sync_channels để nạp kiến thức", self.kb.count())
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
            if channel is None:
                try:
                    channel = await self.fetch_channel(int(row["channel_id"]))
                except discord.HTTPException:
                    continue
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                continue
            q = (row["question"] or "")[:300]
            await channel.send(
                f"⏰ Câu hỏi `#{row['id']}` vẫn Pending > {self.settings.pending_timeout_hours}h "
                f"{mention}\n> {q}\n"
                f"_Mentor: `/resolve noi_dung:... id:{row['id']}`_"
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


def _is_mentor(user: discord.abc.User) -> bool:
    if isinstance(user, discord.Member) and user.guild_permissions.manage_messages:
        return True
    if bot.settings.mentor_user_id and user.id == bot.settings.mentor_user_id:
        return True
    if bot.settings.mentor_role_id and isinstance(user, discord.Member):
        if any(r.id == bot.settings.mentor_role_id for r in user.roles):
            return True
    return False


async def _recent_user_transcript(
    channel: discord.abc.Messageable,
    *,
    limit: int = 25,
    only_author_ids: set[int] | None = None,
) -> str:
    """Lấy tin người dùng gần đây kèm username Discord để trả lời follow-up."""
    lines: list[str] = []
    scan_limit = min(500, max(limit * 8, 80))
    async for message in channel.history(limit=scan_limit):
        if message.author.bot:
            continue
        if only_author_ids is not None and message.author.id not in only_author_ids:
            continue
        text = (message.content or "").strip()
        if not text:
            continue
        display = message.author.display_name
        username = message.author.name
        lines.append(f"{display} (@{username} / id={message.author.id}): {text}")
        if len(lines) >= limit:
            break
    return "\n".join(reversed(lines))


async def _resolve_target_user_ids(
    *,
    question: str,
    channel: discord.abc.Messageable | None,
    extra_ids: list[int] | None = None,
) -> list[int]:
    """Lấy ID người được hỏi (mention / @username chữ), bỏ bot."""
    ids = list(parse_mention_ids(question))
    if extra_ids:
        ids.extend(extra_ids)

    plain = parse_plain_ats(question)
    if plain and channel is not None and isinstance(channel, (discord.TextChannel, discord.Thread)):
        # Map @bombivulun → user id bằng tin gần đây trong kênh
        want = {p.lower() for p in plain}
        found: dict[str, int] = {}
        async for message in channel.history(limit=300):
            if message.author.bot:
                continue
            uname = (message.author.name or "").lower()
            dname = (message.author.display_name or "").lower().replace(" ", "")
            global_name = (getattr(message.author, "global_name", None) or "").lower()
            for key in (uname, dname, global_name):
                if key and key in want and key not in found:
                    found[key] = message.author.id
            if len(found) >= len(want):
                break
        ids.extend(found.values())

    seen: set[int] = set()
    out: list[int] = []
    bot_id = bot.user.id if bot.user else None
    for i in ids:
        if i in seen:
            continue
        if bot_id is not None and i == bot_id:
            continue
        seen.add(i)
        out.append(i)
    return out


async def _handle_question(
    *,
    question: str,
    author_id: int,
    guild_id: int | None,
    channel_id: int,
    message_id: str,
    channel: discord.abc.Messageable | None = None,
    mentioned_user_ids: list[int] | None = None,
) -> str:
    recent_chat = ""
    channel_label = ""
    target_user_chat = ""
    target_user_label = ""
    if channel is not None and isinstance(channel, (discord.TextChannel, discord.Thread)):
        recent_chat = await _recent_user_transcript(channel, limit=25)
        channel_label = f"hội thoại gần đây #{channel.name}"
        target_ids = await _resolve_target_user_ids(
            question=question,
            channel=channel,
            extra_ids=mentioned_user_ids,
        )
        # Bỏ chính người hỏi nếu họ chỉ tag bot + hỏi về người khác
        target_ids = [i for i in target_ids if i != author_id]
        if _is_user_message_lookup(question):
            if not target_ids:
                ats = parse_plain_ats(question)
                hint = f" ({', '.join('@'+a for a in ats)})" if ats else ""
                return (
                    "Mình nhận câu hỏi về tin nhắn của một người, nhưng chưa resolve được "
                    f"user được hỏi{hint}. Hãy **tag mention** họ (chọn từ danh sách Discord) rồi hỏi lại."
                )
            target_user_chat = await _recent_user_transcript(
                channel,
                limit=40,
                only_author_ids=set(target_ids),
            )
            names = ", ".join(f"<@{i}>" for i in target_ids[:3])
            target_user_label = f"tin của {names} trong #{channel.name}"
            if not target_user_chat.strip():
                return (
                    f"Mình đã quét kênh #{channel.name} nhưng chưa thấy tin nhắn "
                    f"(không phải bot) từ {names} trong phạm vi gần đây."
                )

    result = bot.pipeline.ask(
        question,
        recent_chat=recent_chat,
        channel_label=channel_label,
        target_user_chat=target_user_chat,
        target_user_label=target_user_label,
    )
    reply = bot.pipeline.format_discord_reply(
        result,
        mentor_mention=_mentor_mention(),
    )
    if not result.decision.grounded:
        pending_id = await bot.store.add_pending(
            guild_id=str(guild_id) if guild_id else None,
            channel_id=str(channel_id),
            message_id=message_id,
            author_id=str(author_id),
            question=question,
        )
        if pending_id is not None:
            reply += (
                f"\n_Mã hỗ trợ `#{pending_id}` — Mentor dùng "
                f"`/resolve noi_dung:... id:{pending_id}` khi đã trả lời._"
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
            channel=interaction.channel,
            mentioned_user_ids=parse_mention_ids(question),
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
    description="Tóm tắt hội thoại người dùng gần đây trong kênh (bỏ tin bot)",
)
@app_commands.describe(
    so_tin="Số tin người dùng gần nhất để tóm tắt (mặc định 30, tối đa 100)",
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
    # Quét rộng hơn vì bỏ tin bot; dừng khi đủ so_tin tin người dùng
    scan_limit = min(1000, max(int(so_tin) * 5, 50))
    async for message in channel.history(limit=scan_limit):
        if message.author.bot:
            continue
        text = (message.content or "").strip()
        if not text:
            continue
        author = message.author.display_name
        lines.append(f"{author}: {text}")
        if len(lines) >= int(so_tin):
            break

    if not lines:
        await interaction.followup.send(
            "Không thấy tin nhắn người dùng gần đây để tóm tắt. "
            "Nếu kênh có chat thật mà vẫn trống: bật **Message Content Intent** rồi restart bot."
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

    header = (
        f"**Tóm tắt {len(lines)} tin người dùng gần nhất "
        f"trong #{getattr(channel, 'name', 'channel')}** _(đã bỏ tin bot)_"
    )
    if focus.strip():
        header += f"\n_Chỉ nội dung liên quan:_ **{focus.strip()}**"
    header += ":\n"
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
    lines.append(
        "\nMentor dùng `/resolve noi_dung:... id:...` sau khi trả lời xong "
        "(bot sẽ báo lại cho học viên)."
    )
    body = "\n".join(lines)
    if len(body) > 1900:
        body = body[:1900] + "\n…"
    await interaction.response.send_message(body, ephemeral=True)


@app_commands.command(
    name="resolve",
    description="Mentor trả lời xong → đóng Pending và báo lại cho học viên",
)
@app_commands.describe(
    noi_dung="Nội dung Admin/Mentor đã trả lời (bot sẽ gửi lại cho người hỏi)",
    id="ID trong /pending (ưu tiên)",
    author="Hoặc chọn học viên — resolve câu mới nhất của họ",
)
async def resolve(
    interaction: discord.Interaction,
    noi_dung: str,
    id: int | None = None,
    author: discord.Member | None = None,
) -> None:
    if not _is_mentor(interaction.user):
        await interaction.response.send_message(
            "Chỉ Mentor/Admin mới resolve được.",
            ephemeral=True,
        )
        return

    answer = (noi_dung or "").strip()
    if not answer:
        await interaction.response.send_message(
            "Cần điền `noi_dung` — nội dung Admin/Mentor đã trả lời.",
            ephemeral=True,
        )
        return

    row: dict | None = None
    if id is not None:
        row = await bot.store.mark_resolved_by_id(int(id))
        if row is None:
            await interaction.response.send_message(
                f"Không thấy câu `#{id}` đang Pending/Escalated "
                "(đã resolve rồi hoặc sai ID).",
                ephemeral=True,
            )
            return
    elif author is not None:
        row = await bot.store.resolve_latest_for_author(str(author.id))
        if not row:
            await interaction.response.send_message(
                f"{author.mention} không có câu Pending/Escalated.",
                ephemeral=True,
            )
            return
    else:
        await interaction.response.send_message(
            "Cần truyền `id` (từ /pending) hoặc `author`, kèm `noi_dung`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    notified = await _notify_student_resolved(
        row=row,
        resolver=interaction.user,
        answer=answer,
    )
    q = (row.get("question") or "")[:120]
    await interaction.followup.send(
        f"Đã resolve `#{row['id']}`"
        + (" và đã báo học viên." if notified else " (không gửi được tin vào kênh gốc — kiểm tra channel_id).")
        + f"\nCâu hỏi: {q}",
        ephemeral=True,
    )


async def _notify_student_resolved(
    *,
    row: dict,
    resolver: discord.abc.User,
    answer: str,
) -> bool:
    """Gửi vào kênh gốc: Admin đã trả lời câu hỏi của học viên với nội dung sau."""
    channel_id = row.get("channel_id")
    author_id = row.get("author_id")
    if not channel_id or not author_id:
        return False

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            return False
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return False

    question = (row.get("question") or "").strip()
    if len(question) > 300:
        question = question[:300] + "…"
    body_answer = answer.strip()
    if len(body_answer) > 1500:
        body_answer = body_answer[:1500] + "…"

    resolver_name = getattr(resolver, "display_name", None) or resolver.name
    text = (
        f"<@{author_id}> **{resolver_name}** đã trả lời câu hỏi của bạn.\n"
        f"**Câu hỏi:** {question}\n"
        f"**Nội dung trả lời:**\n{body_answer}"
    )
    if len(text) > 1900:
        text = text[:1900] + "\n…"

    # Thử reply đúng tin nhắn gốc nếu còn (không phải interaction:...)
    message_id = str(row.get("message_id") or "")
    if message_id.isdigit():
        try:
            original = await channel.fetch_message(int(message_id))
            await original.reply(text, mention_author=True)
            return True
        except discord.HTTPException:
            pass

    await channel.send(text)
    return True


@app_commands.command(
    name="digest",
    description="Tóm tắt hàng đợi Pending cho Mentor (Signal Layer)",
)
async def digest(interaction: discord.Interaction) -> None:
    if not _is_mentor(interaction.user):
        await interaction.response.send_message(
            "Chỉ Mentor/Admin mới xem digest hàng đợi.",
            ephemeral=True,
        )
        return

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
        bullets.append(f"- `#{row['id']}` [{row['status']}] {q}")
    transcript = "\n".join(bullets)
    try:
        summary = bot.engine.summarize_chat(
            transcript,
            focus=(
                "Đây là hàng đợi câu hỏi Pending/Escalated trên Discord. "
                "Tóm tắt theo nhóm chủ đề, nêu câu nào cần ưu tiên (deadline/điểm/link), "
                "và gợi ý Mentor làm gì tiếp. Nhắc dùng /resolve noi_dung:... id:..."
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
    # Ephemeral cho mentor — tránh spam tag công khai mỗi lần gọi digest
    await interaction.followup.send(body, ephemeral=True)


@app_commands.command(
    name="reindex",
    description="Xoá KB local (không đọc file md). Sau đó dùng /sync_channels",
)
async def reindex(interaction: discord.Interaction) -> None:
    if not interaction.user.guild_permissions.manage_guild:  # type: ignore[union-attr]
        await interaction.response.send_message("Cần quyền Manage Server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    bot.kb.reset()
    await interaction.followup.send(
        "Đã xoá KB. Bot **không** đọc file md/code. "
        "Chạy `/sync_channels` để nạp lại chỉ từ kênh Discord đã cấu hình.",
        ephemeral=True,
    )


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
            mention_ids = [
                u.id for u in message.mentions if (not u.bot) and u.id != (bot.user.id if bot.user else 0)
            ]
            reply = await _handle_question(
                question=question,
                author_id=message.author.id,
                guild_id=message.guild.id if message.guild else None,
                channel_id=message.channel.id,
                message_id=str(message.id),
                channel=message.channel,
                mentioned_user_ids=mention_ids,
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
