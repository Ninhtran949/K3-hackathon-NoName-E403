from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.config import Settings
from app.database import Database

logger = logging.getLogger(__name__)

EXTENSIONS = (
    "app.cogs.assistant",
    "app.cogs.general",
    "app.cogs.notes",
    "app.cogs.moderation",
    "app.cogs.welcome",
)


class BotCommandTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        handler = getattr(self.client, "handle_app_command_error", None)
        if handler is None:
            await super().on_error(interaction, error)
            return
        await handler(interaction, error)


class DiscordStarterBot(commands.Bot):
    def __init__(self, *, settings: Settings, database: Database) -> None:
        intents = discord.Intents.default()
        intents.members = settings.enable_member_intent
        intents.message_content = settings.enable_message_content_intent

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            tree_cls=BotCommandTree,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=True,
                replied_user=False,
            ),
        )
        self.settings = settings
        self.database = database

    async def setup_hook(self) -> None:
        await asyncio.to_thread(self.database.initialize)
        deleted_sources = await asyncio.to_thread(
            self.database.cleanup_expired_sources,
            self.settings.source_retention_days,
        )
        if deleted_sources:
            logger.info("Đã xóa %s nguồn community quá hạn", deleted_sources)
        deleted_cases = await asyncio.to_thread(
            self.database.cleanup_expired_support_cases,
            self.settings.support_case_retention_days,
        )
        if deleted_cases:
            logger.info("Đã xóa %s support case đã xử lý quá hạn", deleted_cases)

        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Đã nạp extension %s", extension)

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Đã đồng bộ %s command cho server test %s",
                len(synced),
                self.settings.guild_id,
            )
        else:
            synced = await self.tree.sync()
            logger.info("Đã đồng bộ %s global command", len(synced))

    async def on_ready(self) -> None:
        if self.user is None:
            return
        logger.info(
            "Bot đã online: %s (ID: %s), đang ở %s server",
            self.user,
            self.user.id,
            len(self.guilds),
        )

    async def handle_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Bạn không có quyền cần thiết để dùng lệnh này."
        elif isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            message = f"Bot đang thiếu quyền: {missing}."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"Bạn hãy thử lại sau {error.retry_after:.1f} giây."
        elif isinstance(error, app_commands.CheckFailure):
            message = "Bạn không thể sử dụng lệnh này tại đây."
        else:
            logger.exception(
                "Slash command gặp lỗi",
                exc_info=(type(error), error, error.__traceback__),
                extra={
                    "command": interaction.command.name if interaction.command else "unknown",
                    "user_id": interaction.user.id,
                },
            )
            message = "Bot gặp lỗi ngoài dự kiến. Chi tiết đã được ghi vào log."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
