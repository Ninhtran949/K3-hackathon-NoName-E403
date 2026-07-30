from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.core_rag_engine.adapters.outbound.support import (
    SqliteSupportRepository,
)
from src.core_rag_engine.application import (
    SupportWorkflow,
    SupportWorkflowConfig,
)
from src.core_rag_engine.domain import (
    EscalationRecord,
    MentorDecisionInput,
    MentorDraft,
    ReviewAction,
    ReviewDecisionKind,
)


def _record(
    review_id: str,
    question: str = "Fix CUDA?",
    *,
    created_at: datetime | None = None,
) -> EscalationRecord:
    return EscalationRecord(
        review_id=review_id,
        question=question,
        author_id="student",
        author_mention="<@student>",
        original_channel_id="100",
        original_message_id="200",
        source_url="https://discord.com/channels/g/100/200",
        mentor_mention="<@&20>",
        created_at=created_at or datetime(2026, 7, 30, 10, tzinfo=UTC),
        draft=MentorDraft(text="Hãy thử giảm batch size."),
    )


def _decision(action: ReviewAction, edited_answer: str = "") -> MentorDecisionInput:
    return MentorDecisionInput(
        support_context_id="thread-1",
        reviewer_id="mentor",
        reviewer_role_ids=("20",),
        can_moderate=False,
        action=action,
        edited_answer=edited_answer,
    )


def test_review_delivery_is_claimed_and_can_be_retried(tmp_path: Path) -> None:
    repository = SqliteSupportRepository(tmp_path / "support.sqlite3")
    repository.create(_record("review-1"))
    assert repository.bind_context("review-1", "thread-1") is True
    workflow = SupportWorkflow(repository, SupportWorkflowConfig())

    first = workflow.decide(_decision(ReviewAction.APPROVE))

    assert first.kind is ReviewDecisionKind.READY_TO_SEND
    assert first.answer == "Hãy thử giảm batch size."
    assert repository.status("review-1") == "sending"

    workflow.complete_delivery("review-1", succeeded=False)
    assert repository.status("review-1") == "pending"

    retry = workflow.decide(
        _decision(ReviewAction.EDIT_AND_SEND, "Bản mentor đã sửa.")
    )
    assert retry.kind is ReviewDecisionKind.READY_TO_SEND
    assert retry.answer == "Bản mentor đã sửa."

    workflow.complete_delivery("review-1", succeeded=True)
    assert repository.status("review-1") == "sent"
    assert workflow.decide(_decision(ReviewAction.APPROVE)).kind is (
        ReviewDecisionKind.ALREADY_RESOLVED
    )


def test_review_reject_requires_routed_mentor_or_moderator(
    tmp_path: Path,
) -> None:
    repository = SqliteSupportRepository(tmp_path / "support.sqlite3")
    repository.create(_record("review-1"))
    repository.bind_context("review-1", "thread-1")
    workflow = SupportWorkflow(repository, SupportWorkflowConfig())
    unauthorized = MentorDecisionInput(
        support_context_id="thread-1",
        reviewer_id="other",
        reviewer_role_ids=("99",),
        can_moderate=False,
        action=ReviewAction.REJECT,
    )

    assert workflow.decide(unauthorized).kind is ReviewDecisionKind.UNAUTHORIZED
    assert workflow.decide(_decision(ReviewAction.REJECT)).kind is (
        ReviewDecisionKind.REJECTED
    )
    assert repository.status("review-1") == "rejected"


def test_digest_groups_hot_questions_and_only_sends_once_per_day(
    tmp_path: Path,
) -> None:
    repository = SqliteSupportRepository(tmp_path / "support.sqlite3")
    now = datetime(2026, 7, 30, 16, 30, tzinfo=UTC)
    repository.create(_record("r1", "Fix CUDA?", created_at=now - timedelta(hours=3)))
    repository.create(_record("r2", "fix cuda ?", created_at=now - timedelta(hours=1)))
    repository.create(_record("r3", "Deadline?", created_at=now))
    workflow = SupportWorkflow(
        repository,
        SupportWorkflowConfig(
            digest_timezone="Asia/Bangkok",
            digest_hour=23,
            digest_minute=0,
        ),
    )

    digest = workflow.build_digest(now)

    assert digest is not None
    assert digest.pending_count == 3
    assert digest.items[0].count == 2
    assert digest.items[0].question == "Fix CUDA?"

    workflow.mark_digest_sent(digest.report_date)
    assert workflow.build_digest(now) is None
    assert workflow.build_digest(now, force=True) is not None
