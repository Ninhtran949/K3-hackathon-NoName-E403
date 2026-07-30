from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class ModerationCog(commands.Cog):
    @app_commands.command(
        name="clear",
        description="Xóa một số tin nhắn gần nhất trong kênh",
    )
    @app_commands.describe(amount="Số tin nhắn cần xóa, từ 1 đến 100")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def clear_messages(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
    ) -> None:
        channel = interaction.channel
        if channel is None or not hasattr(channel, "purge"):
            await interaction.response.send_message(
                "Không thể xóa tin nhắn trong loại kênh này.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await channel.purge(
            limit=amount,
            reason=f"Yêu cầu bởi {interaction.user} ({interaction.user.id})",
        )
        await interaction.followup.send(
            f"🧹 Đã xóa **{len(deleted)}** tin nhắn.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog())
