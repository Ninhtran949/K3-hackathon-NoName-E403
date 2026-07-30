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

# Map dấu tiếng Việt → không dấu (để khớp "deadline nop bai" ↔ "deadline nộp bài")
_VI_MAP = str.maketrans(
    {
        "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
        "đ": "d",
        "À": "a", "Á": "a", "Ả": "a", "Ã": "a", "Ạ": "a",
        "Ă": "a", "Ằ": "a", "Ắ": "a", "Ẳ": "a", "Ẵ": "a", "Ặ": "a",
        "Â": "a", "Ầ": "a", "Ấ": "a", "Ẩ": "a", "Ẫ": "a", "Ậ": "a",
        "È": "e", "É": "e", "Ẻ": "e", "Ẽ": "e", "Ẹ": "e",
        "Ê": "e", "Ề": "e", "Ế": "e", "Ể": "e", "Ễ": "e", "Ệ": "e",
        "Ì": "i", "Í": "i", "Ỉ": "i", "Ĩ": "i", "Ị": "i",
        "Ò": "o", "Ó": "o", "Ỏ": "o", "Õ": "o", "Ọ": "o",
        "Ô": "o", "Ồ": "o", "Ố": "o", "Ổ": "o", "Ỗ": "o", "Ộ": "o",
        "Ơ": "o", "Ờ": "o", "Ớ": "o", "Ở": "o", "Ỡ": "o", "Ợ": "o",
        "Ù": "u", "Ú": "u", "Ủ": "u", "Ũ": "u", "Ụ": "u",
        "Ư": "u", "Ừ": "u", "Ứ": "u", "Ử": "u", "Ữ": "u", "Ự": "u",
        "Ỳ": "y", "Ý": "y", "Ỷ": "y", "Ỹ": "y", "Ỵ": "y",
        "Đ": "d",
    }
)

# Từ viết tắt / biến thể thường gặp khi gõ tắt
_QUERY_EXPAND: dict[str, tuple[str, ...]] = {
    "dl": ("deadline",),
    "deadl": ("deadline",),
    "nopbai": ("nop", "bai", "deadline"),
    "han": ("deadline", "han", "nop"),
    "hn": ("hom", "nay"),
    "ntn": ("nhu", "the", "nao"),
    "nhiu": ("nhieu",),
    "bao": ("bao", "nhieu"),
    "ko": ("khong",),
    "hok": ("khong",),
    "kg": ("khong",),
    "dc": ("duoc",),
    "đc": ("duoc",),
    "duoc": ("duoc",),
    "vs": ("voi",),
    "mik": ("minh",),
    "mk": ("minh",),
    "bai": ("bai", "assignment"),
    "zoom": ("zoom", "link"),
}


def fold_vi(text: str) -> str:
    return (text or "").translate(_VI_MAP).lower()


def _tokens(text: str) -> list[str]:
    """Token không dấu + mở rộng viết tắt để khớp câu gõ lỏng."""
    folded = fold_vi(text)
    raw = [t for t in _TOKEN.findall(folded)]
    out: list[str] = []
    for t in raw:
        out.append(t)
        # gộp nếu người dùng viết dính: nopbai, deadline...
        if t in _QUERY_EXPAND:
            out.extend(_QUERY_EXPAND[t])
    return out


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


def _is_channel_source(source: str) -> bool:
    """Chỉ chấp nhận nguồn từ kênh Discord đã sync (#channel...), không nhận file .md/.txt/code."""
    s = (source or "").strip().lower()
    if not s.startswith("#"):
        return False
    if s.endswith((".md", ".txt", ".py", ".json", ".csv")):
        return False
    return True


class KnowledgeBase:
    """Lightweight local KB (JSON + TF cosine) — chỉ chứa tin kênh Discord đã sync."""

    def __init__(self, persist_dir: Path, collection_name: str = "course_knowledge") -> None:
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.persist_dir / f"{collection_name}.json"
        self._chunks: dict[str, Chunk] = {}
        self._load()
        removed = self.purge_non_channel_sources()
        if removed:
            # đã lưu trong purge
            pass

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

    def purge_non_channel_sources(self) -> int:
        """Xoá mọi chunk lấy từ file md/txt/code — chỉ giữ nguồn #kênh Discord."""
        before = len(self._chunks)
        self._chunks = {
            k: v for k, v in self._chunks.items() if _is_channel_source(v.source)
        }
        removed = before - len(self._chunks)
        if removed:
            self._save()
        return removed

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        kept = 0
        for c in chunks:
            if not _is_channel_source(c.source):
                continue
            self._chunks[c.doc_id] = c
            kept += 1
        if kept:
            self._save()
        return kept

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
            if not _is_channel_source(chunk.source):
                continue
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
