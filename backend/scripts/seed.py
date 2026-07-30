"""Seed static FAQ/text files into the configured Chroma collection."""

from __future__ import annotations

from src.bootstrap import build_container
from src.core_rag_engine.application import load_seed_documents


def main() -> None:
    container = build_container()
    seed_directory = container.settings.resolve_path(
        container.project_root,
        container.settings.seed_data_dir,
    )
    documents = load_seed_documents(seed_directory)
    count = container.engine.ingest_documents(documents)
    print(f"Seeded {count} documents into ChromaDB.")


if __name__ == "__main__":
    main()
