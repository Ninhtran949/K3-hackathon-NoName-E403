from __future__ import annotations

import logging

import discord
from discord.ext import commands

from app.config import Settings

logger = logging.getLogger(__name__)


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        channel_id = self.settings.welcome_channel_id
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.abc.Messageable):
            logger.warning("Không tìm thấy welcome channel ID %s", channel_id)
            return

        try:
            await channel.send(f"Chào mừng {member.mention} đến với **{member.guild.name}**! 🎉")
        except discord.Forbidden:
            logger.warning("Bot không có quyền gửi tin nhắn vào welcome channel")


async def setup(bot: commands.Bot) -> None:
    settings = bot.settings
    await bot.add_cog(WelcomeCog(bot, settings))
