"""Environment-backed runtime settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    discord_bot_token: str = ""
    discord_guild_id: str = ""
    discord_monitored_channel_ids: str = ""
    discord_support_channel_id: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    mentor_research_model: str = "gemini-2.5-flash"

    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "student_assistant_knowledge"

    app_config_path: str = "./configs/app.yaml"
    routing_config_path: str = "./configs/routing.yaml"
    onboarding_config_path: str = "./configs/onboarding.yaml"
    onboarding_state_db_path: str = "./data/state/onboarding.sqlite3"
    support_state_db_path: str = "./data/state/support.sqlite3"
    system_prompt_path: str = "./prompts/rag_answer.md"
    mentor_draft_prompt_path: str = "./prompts/mentor_draft.md"
    seed_data_dir: str = "./data/seed"
    seed_on_startup: bool = True

    @classmethod
    def load(cls, project_root: Path) -> "Settings":
        return cls(_env_file=project_root / ".env", _env_file_encoding="utf-8")

    def validate_runtime(self) -> None:
        required = {
            "DISCORD_BOT_TOKEN": self.discord_bot_token,
            "DISCORD_GUILD_ID": self.discord_guild_id,
            "DISCORD_MONITORED_CHANNEL_IDS": self.discord_monitored_channel_ids,
            "DISCORD_SUPPORT_CHANNEL_ID": self.discord_support_channel_id,
            "GEMINI_API_KEY": self.gemini_api_key,
            "GEMINI_MODEL": self.gemini_model,
            "MENTOR_RESEARCH_MODEL": self.mentor_research_model,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(
                "Missing required environment variables: " + ", ".join(missing)
            )
        self.monitored_channel_ids()
        self.support_channel_id()

    def monitored_channel_ids(self) -> frozenset[int]:
        values = {
            self._parse_snowflake(item.strip(), "DISCORD_MONITORED_CHANNEL_IDS")
            for item in self.discord_monitored_channel_ids.split(",")
            if item.strip()
        }
        if not values:
            raise ValueError("DISCORD_MONITORED_CHANNEL_IDS cannot be empty")
        return frozenset(values)

    def support_channel_id(self) -> int:
        return self._parse_snowflake(
            self.discord_support_channel_id,
            "DISCORD_SUPPORT_CHANNEL_ID",
        )

    def resolve_path(self, project_root: Path, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (project_root / path).resolve()

    @staticmethod
    def _parse_snowflake(value: str, variable_name: str) -> int:
        try:
            snowflake = int(value)
        except ValueError as error:
            raise ValueError(f"{variable_name} must contain Discord IDs") from error
        if snowflake <= 0:
            raise ValueError(f"{variable_name} must contain positive Discord IDs")
        return snowflake
