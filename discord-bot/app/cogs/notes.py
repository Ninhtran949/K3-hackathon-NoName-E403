from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from app.database import Database, NoteLimitReachedError


class NotesCog(
    commands.GroupCog,
    group_name="note",
    group_description="Quản lý ghi chú cá nhân",
):
    def __init__(self, database: Database, max_notes_per_user: int) -> None:
        self.database = database
        self.max_notes_per_user = max_notes_per_user

    @app_commands.command(name="add", description="Lưu một ghi chú cá nhân")
    @app_commands.describe(content="Nội dung cần ghi nhớ")
    async def add_note(
        self,
        interaction: discord.Interaction,
        content: str,
    ) -> None:
        normalized_content = content.strip()
        if not normalized_content:
            await interaction.response.send_message(
                "Nội dung ghi chú không được để trống.",
                ephemeral=True,
            )
            return
        if len(normalized_content) > 500:
            await interaction.response.send_message(
                "Ghi chú được phép dài tối đa 500 ký tự.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            note = await asyncio.to_thread(
                self.database.add_note,
                interaction.user.id,
                normalized_content,
                limit=self.max_notes_per_user,
            )
        except NoteLimitReachedError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Đã lưu ghi chú `#{note.id}`.",
            ephemeral=True,
        )

    @app_commands.command(name="list", description="Xem các ghi chú gần nhất")
    async def list_notes(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        notes = await asyncio.to_thread(
            self.database.list_notes,
            interaction.user.id,
            limit=10,
        )

        if not notes:
            await interaction.followup.send(
                "Bạn chưa có ghi chú nào.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Ghi chú của bạn",
            description="Hiển thị tối đa 10 ghi chú gần nhất.",
            color=discord.Color.blurple(),
        )
        for note in notes:
            embed.add_field(
                name=f"#{note.id} · {note.created_at} UTC",
                value=note.content,
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="delete", description="Xóa một ghi chú")
    @app_commands.describe(note_id="ID hiển thị trong lệnh /note list")
    async def delete_note(
        self,
        interaction: discord.Interaction,
        note_id: app_commands.Range[int, 1],
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        deleted = await asyncio.to_thread(
            self.database.delete_note,
            interaction.user.id,
            note_id,
        )

        message = (
            f"🗑️ Đã xóa ghi chú `#{note_id}`."
            if deleted
            else "Không tìm thấy ghi chú đó hoặc ghi chú không thuộc về bạn."
        )
        await interaction.followup.send(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    database = bot.database
    settings = bot.settings
    await bot.add_cog(NotesCog(database, settings.max_notes_per_user))
