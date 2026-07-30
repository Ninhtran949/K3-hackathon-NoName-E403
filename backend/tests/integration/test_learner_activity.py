from datetime import UTC, datetime
from pathlib import Path

from src.core_rag_engine.adapters.outbound.activity import (
    SqliteLearnerActivityAdapter,
)
from src.core_rag_engine.domain import MessageInput


def _message(message_id: str, author_id: str = "u1") -> MessageInput:
    return MessageInput(
        message_id=message_id,
        content="Câu hỏi?",
        author_id=author_id,
        author_mention=f"<@{author_id}>",
        channel_id="c1",
        source_url="https://discord.com/channels/g/c/m",
        created_at=datetime.now(UTC),
    )


def test_first_question_state_survives_adapter_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "state" / "onboarding.sqlite3"
    first_adapter = SqliteLearnerActivityAdapter(database_path)

    assert first_adapter.claim_first_question(_message("m1")) is True
    assert first_adapter.claim_first_question(_message("m2")) is False

    restarted_adapter = SqliteLearnerActivityAdapter(database_path)
    assert restarted_adapter.claim_first_question(_message("m3")) is False
    assert restarted_adapter.claim_first_question(
        _message("m4", author_id="u2")
    ) is True
