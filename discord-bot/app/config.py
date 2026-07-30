from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


def _optional_positive_int(value: str | None, field_name: str) -> int | None:
    if value is None or not value.strip():
        return None

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field_name} phải là một số nguyên") from error

    if parsed <= 0:
        raise ValueError(f"{field_name} phải lớn hơn 0")
    return parsed


def _positive_int(value: str | None, field_name: str, default: int) -> int:
    if value is None or not value.strip():
        return default
    parsed = _optional_positive_int(value, field_name)
    assert parsed is not None
    return parsed


def _float_in_range(
    value: str | None,
    field_name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if value is None or not value.strip():
        return default

    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{field_name} phải là một số") from error

    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field_name} phải nằm trong khoảng {minimum} đến {maximum}")
    return parsed


def _positive_int_set(value: str | None, field_name: str) -> frozenset[int]:
    if value is None or not value.strip():
        return frozenset()

    parsed_values: set[int] = set()
    for item in value.split(","):
        parsed = _optional_positive_int(item.strip(), field_name)
        if parsed is not None:
            parsed_values.add(parsed)
    return frozenset(parsed_values)


def _boolean(value: str | None, field_name: str, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} phải là true hoặc false")


def _resolve_path(base_dir: Path, value: str | None, default: str) -> Path:
    path = Path(value.strip() if value and value.strip() else default)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    guild_id: int | None
    qa_channel_ids: frozenset[int]
    announcement_channel_ids: frozenset[int]
    support_channel_id: int | None
    admin_role_ids: frozenset[int]
    mentor_role_ids: frozenset[int]
    default_support_role_id: int | None
    enable_message_content_intent: bool
    welcome_channel_id: int | None
    enable_member_intent: bool
    gemini_api_key: str | None
    gemini_model: str
    routing_path: Path
    top_k: int
    similarity_threshold: float
    source_retention_days: int
    support_case_retention_days: int
    max_reindex_messages: int
    ask_ephemeral: bool
    database_path: Path
    log_dir: Path
    log_level: str
    max_notes_per_user: int

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        base_dir: Path | None = None,
    ) -> Settings:
        values = os.environ if environ is None else environ
        root = (base_dir or Path.cwd()).resolve()

        legacy_token = values.get("DISCORD_TOKEN", "").strip()
        spec_token = values.get("DISCORD_BOT_TOKEN", "").strip()
        if legacy_token and spec_token and legacy_token != spec_token:
            raise ValueError("DISCORD_TOKEN và DISCORD_BOT_TOKEN đang có giá trị khác nhau")
        token = spec_token or legacy_token
        if not token:
            raise ValueError("Bạn chưa điền DISCORD_TOKEN hoặc DISCORD_BOT_TOKEN trong file .env")

        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level not in allowed_levels:
            raise ValueError("LOG_LEVEL phải là DEBUG, INFO, WARNING, ERROR hoặc CRITICAL")

        return cls(
            token=token,
            guild_id=_optional_positive_int(
                values.get("DISCORD_GUILD_ID"),
                "DISCORD_GUILD_ID",
            ),
            qa_channel_ids=_positive_int_set(
                values.get("DISCORD_QA_CHANNEL_IDS"),
                "DISCORD_QA_CHANNEL_IDS",
            ),
            announcement_channel_ids=_positive_int_set(
                values.get("DISCORD_ANNOUNCEMENT_CHANNEL_IDS"),
                "DISCORD_ANNOUNCEMENT_CHANNEL_IDS",
            ),
            support_channel_id=_optional_positive_int(
                values.get("DISCORD_SUPPORT_CHANNEL_ID"),
                "DISCORD_SUPPORT_CHANNEL_ID",
            ),
            admin_role_ids=_positive_int_set(
                values.get("DISCORD_ADMIN_ROLE_IDS"),
                "DISCORD_ADMIN_ROLE_IDS",
            ),
            mentor_role_ids=_positive_int_set(
                values.get("DISCORD_MENTOR_ROLE_IDS"),
                "DISCORD_MENTOR_ROLE_IDS",
            ),
            default_support_role_id=_optional_positive_int(
                values.get("DISCORD_DEFAULT_SUPPORT_ROLE_ID"),
                "DISCORD_DEFAULT_SUPPORT_ROLE_ID",
            ),
            enable_message_content_intent=_boolean(
                values.get("ENABLE_MESSAGE_CONTENT_INTENT"),
                "ENABLE_MESSAGE_CONTENT_INTENT",
            ),
            welcome_channel_id=_optional_positive_int(
                values.get("WELCOME_CHANNEL_ID"),
                "WELCOME_CHANNEL_ID",
            ),
            enable_member_intent=_boolean(
                values.get("ENABLE_MEMBER_INTENT"),
                "ENABLE_MEMBER_INTENT",
            ),
            gemini_api_key=values.get("GEMINI_API_KEY", "").strip() or None,
            gemini_model=(values.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"),
            routing_path=_resolve_path(
                root,
                values.get("ROUTING_CONFIG_PATH"),
                "config/routing.json",
            ),
            top_k=_positive_int(values.get("TOP_K"), "TOP_K", 5),
            similarity_threshold=_float_in_range(
                values.get("SIMILARITY_THRESHOLD"),
                "SIMILARITY_THRESHOLD",
                0.55,
                minimum=0.0,
                maximum=1.0,
            ),
            source_retention_days=_positive_int(
                values.get("SOURCE_RETENTION_DAYS"),
                "SOURCE_RETENTION_DAYS",
                30,
            ),
            support_case_retention_days=_positive_int(
                values.get("SUPPORT_CASE_RETENTION_DAYS"),
                "SUPPORT_CASE_RETENTION_DAYS",
                90,
            ),
            max_reindex_messages=_positive_int(
                values.get("MAX_REINDEX_MESSAGES"),
                "MAX_REINDEX_MESSAGES",
                200,
            ),
            ask_ephemeral=_boolean(
                values.get("ASK_EPHEMERAL"),
                "ASK_EPHEMERAL",
                default=True,
            ),
            database_path=_resolve_path(
                root,
                values.get("DATABASE_PATH"),
                "data/bot.db",
            ),
            log_dir=_resolve_path(root, values.get("LOG_DIR"), "logs"),
            log_level=log_level,
            max_notes_per_user=_positive_int(
                values.get("MAX_NOTES_PER_USER"),
                "MAX_NOTES_PER_USER",
                50,
            ),
        )
