from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Độ trễ hiện tại: **{latency_ms} ms**")

    @app_commands.command(name="hello", description="Bot gửi lời chào đến bạn")
    async def hello(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Xin chào {interaction.user.mention}! Mình đã sẵn sàng 🤖"
        )

    @app_commands.command(
        name="userinfo",
        description="Xem thông tin của một thành viên",
    )
    @app_commands.describe(member="Thành viên cần xem; để trống để xem chính bạn")
    @app_commands.guild_only()
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        selected = member
        if selected is None:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "Lệnh này chỉ dùng được trong server.",
                    ephemeral=True,
                )
                return
            selected = interaction.user

        embed = discord.Embed(
            title=f"Thông tin của {selected.display_name}",
            color=selected.color,
        )
        embed.set_thumbnail(url=selected.display_avatar.url)
        embed.add_field(name="Tên tài khoản", value=str(selected), inline=False)
        embed.add_field(name="User ID", value=str(selected.id))
        embed.add_field(
            name="Tham gia Discord",
            value=discord.utils.format_dt(selected.created_at, style="D"),
        )
        if selected.joined_at:
            embed.add_field(
                name="Vào server",
                value=discord.utils.format_dt(selected.joined_at, style="D"),
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog(bot))
