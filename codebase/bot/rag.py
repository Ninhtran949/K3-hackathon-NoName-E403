from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Chunk:
    doc_id: str
    text: str
    source: str
    jump_url: str = ""


_TOKEN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _chunk_text(text: str, source: str, size: int = 700, overlap: int = 100) -> list[Chunk]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + size)
        piece = text[start:end].strip()
        if piece:
            raw = f"{source}:{idx}:{piece[:40]}"
            doc_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
            chunks.append(Chunk(doc_id=doc_id, text=piece, source=source))
            idx += 1
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class KnowledgeBase:
    """Lightweight local KB (JSON + TF cosine) — không cần ChromaDB."""

    def __init__(self, persist_dir: Path, collection_name: str = "course_knowledge") -> None:
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.persist_dir / f"{collection_name}.json"
        self._chunks: dict[str, Chunk] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._chunks = {
            item["doc_id"]: Chunk(
                doc_id=item["doc_id"],
                text=item["text"],
                source=item.get("source", ""),
                jump_url=item.get("jump_url", ""),
            )
            for item in data
        }

    def _save(self) -> None:
        payload = [asdict(c) for c in self._chunks.values()]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def count(self) -> int:
        return len(self._chunks)

    def reset(self) -> None:
        self._chunks = {}
        if self.path.exists():
            self.path.unlink()

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        for c in chunks:
            self._chunks[c.doc_id] = c
        self._save()
        return len(chunks)

    def ingest_markdown_dir(self, folder: Path) -> int:
        total = 0
        for path in sorted(folder.glob("**/*")):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            chunks = _chunk_text(text, source=str(path.name))
            total += self.upsert_chunks(chunks)
        return total

    def upsert_message(
        self,
        *,
        message_id: str,
        content: str,
        channel_name: str,
        jump_url: str,
    ) -> int:
        source = f"#{channel_name}"
        chunks = _chunk_text(content, source=source, size=500, overlap=80)
        for c in chunks:
            c.doc_id = hashlib.sha1(f"{message_id}:{c.doc_id}".encode()).hexdigest()[:16]
            c.jump_url = jump_url
            c.source = f"{source} · msg:{message_id}"
        return self.upsert_chunks(chunks)

    def query(self, question: str, top_k: int = 4) -> list[dict]:
        if not self._chunks:
            return []
        q = Counter(_tokens(question))
        scored: list[tuple[float, Chunk]] = []
        for chunk in self._chunks.values():
            sim = _cosine(q, Counter(_tokens(chunk.text)))
            if sim > 0:
                scored.append((sim, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict] = []
        for sim, chunk in scored[:top_k]:
            out.append(
                {
                    "text": chunk.text,
                    "source": chunk.source,
                    "jump_url": chunk.jump_url,
                    "similarity": sim,
                }
            )
        return out
