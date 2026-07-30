import asyncio
from pathlib import Path
from types import SimpleNamespace

import discord
from discord.ext import commands

from app.cogs.assistant import AssistantCog, _numeric_role_id, _truncate
from app.config import Settings
from app.database import Database


def test_assistant_cog_initializes_without_optional_ai_key(tmp_path: Path) -> None:
    routing_path = tmp_path / "routing.json"
    routing_path.write_text(
        '{"routes": [], "default_role_id": null}',
        encoding="utf-8",
    )
    settings = Settings.from_env(
        {
            "DISCORD_TOKEN": "test-token",
            "ROUTING_CONFIG_PATH": str(routing_path),
            "DATABASE_PATH": str(tmp_path / "bot.db"),
        },
        base_dir=tmp_path,
    )
    database = Database(settings.database_path)
    database.initialize()
    bot = SimpleNamespace(settings=settings, database=database)

    cog = AssistantCog(bot)  # type: ignore[arg-type]

    assert cog.qa.answer_generator is None
    assert cog.routing.routes == ()


def test_role_id_and_truncation_helpers_are_conservative() -> None:
    assert _numeric_role_id(123) == 123
    assert _numeric_role_id(" 456 ") == 456
    assert _numeric_role_id("MENTOR_ROLE_ID") is None
    assert _numeric_role_id(True) is None
    assert _truncate("abcdef", 4) == "abc…"


def test_cog_load_starts_and_unload_stops_retention_task(tmp_path: Path) -> None:
    routing_path = tmp_path / "routing.json"
    routing_path.write_text(
        '{"routes": [], "default_role_id": null}',
        encoding="utf-8",
    )
    settings = Settings.from_env(
        {
            "DISCORD_TOKEN": "test-token",
            "ROUTING_CONFIG_PATH": str(routing_path),
            "DATABASE_PATH": str(tmp_path / "bot.db"),
        },
        base_dir=tmp_path,
    )
    database = Database(settings.database_path)
    database.initialize()

    async def exercise_lifecycle() -> None:
        bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
        bot.settings = settings  # type: ignore[attr-defined]
        bot.database = database  # type: ignore[attr-defined]
        cog = AssistantCog(bot)

        await bot.add_cog(cog)
        assert cog.cleanup_expired_sources.is_running()
        await bot.remove_cog(cog.qualified_name)
        await asyncio.sleep(0)
        assert not cog.cleanup_expired_sources.is_running()
        await bot.close()

    asyncio.run(exercise_lifecycle())
