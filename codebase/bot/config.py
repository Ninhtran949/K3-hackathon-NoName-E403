from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _csv_ids(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    discord_token: str
    guild_id: int | None
    knowledge_channel_ids: list[int]
    mentor_user_id: int | None
    mentor_role_id: int | None
    ask_channel_id: int | None
    gemini_model: str
    similarity_threshold: float
    top_k: int
    pending_timeout_hours: int
    kb_dir: Path
    sqlite_path: Path
    knowledge_dir: Path


def load_settings() -> Settings:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong codebase/.env")

    guild_raw = os.getenv("DISCORD_GUILD_ID", "").strip()
    ask_raw = os.getenv("ASK_CHANNEL_ID", "").strip()
    mentor_user_raw = os.getenv("MENTOR_USER_ID", "").strip()
    mentor_raw = os.getenv("MENTOR_ROLE_ID", "").strip()

    return Settings(
        gemini_api_key=key,
        discord_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
        guild_id=int(guild_raw) if guild_raw else None,
        knowledge_channel_ids=_csv_ids(os.getenv("KNOWLEDGE_CHANNEL_IDS", "")),
        mentor_user_id=int(mentor_user_raw) if mentor_user_raw else None,
        mentor_role_id=int(mentor_raw) if mentor_raw else None,
        ask_channel_id=int(ask_raw) if ask_raw else None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.12")),
        top_k=int(os.getenv("TOP_K", "4")),
        pending_timeout_hours=int(os.getenv("PENDING_TIMEOUT_HOURS", "6")),
        kb_dir=ROOT / "kb_store",
        sqlite_path=ROOT / "data" / "bot.db",
        knowledge_dir=ROOT / "knowledge",
    )
