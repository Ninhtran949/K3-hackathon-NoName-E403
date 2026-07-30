"""Load small static seed documents without coupling to a vector database."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain import IngestDocument


def load_seed_documents(directory: Path) -> list[IngestDocument]:
    documents: list[IngestDocument] = []
    for path in sorted(directory.glob("*")):
        if path.suffix.casefold() == ".json":
            documents.extend(_load_json(path))
        elif path.suffix.casefold() in {".md", ".txt"}:
            documents.extend(_load_text(path))
    return documents


def _load_json(path: Path) -> list[IngestDocument]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Seed JSON must contain a list: {path}")
    return [
        IngestDocument(
            document_id=f"seed:{item.get('id', index)}",
            text=str(item["text"]).strip(),
            title=str(item.get("title", path.name)),
            source_url=str(item.get("source_url", "")),
            metadata={"seed_file": path.name},
        )
        for index, item in enumerate(payload, start=1)
    ]


def _load_text(path: Path, chunk_size: int = 1200) -> list[IngestDocument]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    paragraphs = [part.strip() for part in content.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > chunk_size:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)

    return [
        IngestDocument(
            document_id=f"seed:{path.stem}:{index}",
            text=chunk,
            title=f"{path.name} — phần {index}",
            metadata={"seed_file": path.name},
        )
        for index, chunk in enumerate(chunks, start=1)
    ]
