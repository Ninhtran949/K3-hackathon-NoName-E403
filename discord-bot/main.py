from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

from app.bot import DiscordStarterBot
from app.config import Settings
from app.database import Database
from app.logging_config import configure_logging


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    try:
        settings = Settings.from_env(base_dir=project_dir)
    except ValueError as error:
        raise SystemExit(f"Lỗi cấu hình: {error}") from error

    configure_logging(settings.log_dir, settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Đang khởi động Discord bot")

    database = Database(settings.database_path)
    bot = DiscordStarterBot(settings=settings, database=database)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
