from pathlib import Path

import pytest

from app.config import Settings


def test_settings_requires_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DISCORD_TOKEN"):
        Settings.from_env({}, base_dir=tmp_path)


def test_settings_parses_values_and_resolves_paths(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "DISCORD_TOKEN": "secret",
            "DISCORD_GUILD_ID": "123",
            "WELCOME_CHANNEL_ID": "456",
            "DISCORD_QA_CHANNEL_IDS": "10, 11,10",
            "DISCORD_ANNOUNCEMENT_CHANNEL_IDS": "12",
            "DISCORD_SUPPORT_CHANNEL_ID": "13",
            "DISCORD_ADMIN_ROLE_IDS": "20,21",
            "DISCORD_MENTOR_ROLE_IDS": "22",
            "DISCORD_DEFAULT_SUPPORT_ROLE_ID": "23",
            "ENABLE_MESSAGE_CONTENT_INTENT": "yes",
            "ENABLE_MEMBER_INTENT": "true",
            "ANTHROPIC_API_KEY": "anthropic-secret",
            "ANTHROPIC_MODEL": "test-model",
            "ROUTING_CONFIG_PATH": "config/test-routing.json",
            "TOP_K": "7",
            "SIMILARITY_THRESHOLD": "0.61",
            "SOURCE_RETENTION_DAYS": "14",
            "SUPPORT_CASE_RETENTION_DAYS": "45",
            "MAX_REINDEX_MESSAGES": "150",
            "ASK_EPHEMERAL": "true",
            "DATABASE_PATH": "state/test.db",
            "LOG_LEVEL": "debug",
            "MAX_NOTES_PER_USER": "12",
        },
        base_dir=tmp_path,
    )

    assert settings.token == "secret"
    assert settings.guild_id == 123
    assert settings.qa_channel_ids == frozenset({10, 11})
    assert settings.announcement_channel_ids == frozenset({12})
    assert settings.support_channel_id == 13
    assert settings.admin_role_ids == frozenset({20, 21})
    assert settings.mentor_role_ids == frozenset({22})
    assert settings.default_support_role_id == 23
    assert settings.enable_message_content_intent is True
    assert settings.welcome_channel_id == 456
    assert settings.enable_member_intent is True
    assert settings.anthropic_api_key == "anthropic-secret"
    assert settings.anthropic_model == "test-model"
    assert settings.routing_path == (tmp_path / "config/test-routing.json").resolve()
    assert settings.top_k == 7
    assert settings.similarity_threshold == 0.61
    assert settings.source_retention_days == 14
    assert settings.support_case_retention_days == 45
    assert settings.max_reindex_messages == 150
    assert settings.ask_ephemeral is True
    assert settings.database_path == (tmp_path / "state/test.db").resolve()
    assert settings.log_level == "DEBUG"
    assert settings.max_notes_per_user == 12


@pytest.mark.parametrize("value", ["maybe", "2", "enabled"])
def test_settings_rejects_invalid_boolean(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError, match="ENABLE_MEMBER_INTENT"):
        Settings.from_env(
            {
                "DISCORD_TOKEN": "secret",
                "ENABLE_MEMBER_INTENT": value,
            },
            base_dir=tmp_path,
        )


def test_settings_accepts_spec_token_alias(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {"DISCORD_BOT_TOKEN": "spec-token"},
        base_dir=tmp_path,
    )

    assert settings.token == "spec-token"


def test_settings_rejects_conflicting_token_aliases(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="giá trị khác nhau"):
        Settings.from_env(
            {
                "DISCORD_TOKEN": "old-token",
                "DISCORD_BOT_TOKEN": "new-token",
            },
            base_dir=tmp_path,
        )


@pytest.mark.parametrize("value", ["-0.1", "1.1", "not-a-number"])
def test_settings_rejects_invalid_similarity_threshold(
    tmp_path: Path,
    value: str,
) -> None:
    with pytest.raises(ValueError, match="SIMILARITY_THRESHOLD"):
        Settings.from_env(
            {
                "DISCORD_TOKEN": "secret",
                "SIMILARITY_THRESHOLD": value,
            },
            base_dir=tmp_path,
        )
