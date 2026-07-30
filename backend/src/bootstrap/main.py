"""Executable composition root for the Discord bot."""

from __future__ import annotations

import logging

from ..core_rag_engine.application import load_seed_documents
from ..interfaces.discord import create_discord_client
from .container import build_container


def main() -> None:
    container = build_container()
    logging.basicConfig(
        level=container.settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    for noisy_logger in ("httpx", "sentence_transformers", "huggingface_hub"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    if container.settings.seed_on_startup:
        seed_directory = container.settings.resolve_path(
            container.project_root,
            container.settings.seed_data_dir,
        )
        documents = load_seed_documents(seed_directory)
        count = container.engine.ingest_documents(documents)
        logging.getLogger(__name__).info("Seeded %s documents", count)

    client = create_discord_client(
        engine=container.engine,
        support_workflow=container.support_workflow,
        monitored_channel_ids=container.settings.monitored_channel_ids(),
        support_channel_id=container.settings.support_channel_id(),
    )
    client.run(container.settings.discord_bot_token, log_handler=None)


if __name__ == "__main__":
    main()
