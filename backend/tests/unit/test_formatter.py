from src.core_rag_engine.domain import (
    AnswerSource,
    Confidence,
    DigestItem,
    DigestResult,
    MentorDraft,
    OnboardingSuggestion,
    OutcomeKind,
    ProcessingResult,
    ReviewDecisionKind,
    ReviewDecisionResult,
)
from src.interfaces.discord.formatter import (
    format_answer,
    format_approved_answer,
    format_digest,
    format_escalation,
    format_support_ticket,
)
from src.interfaces.discord.bot import _forum_post_title
from src.interfaces.discord.bot import _parse_review_command
from src.core_rag_engine.domain import ReviewAction
from datetime import UTC, datetime


def test_answer_formatter_includes_clickable_source() -> None:
    result = ProcessingResult(
        kind=OutcomeKind.ANSWERED,
        answer="Deadline là 23:59.",
        confidence=Confidence.HIGH,
        sources=(
            AnswerSource(
                document_id="doc-1",
                title="Thông báo",
                source_url="https://discord.com/channels/g/c/m",
            ),
        ),
    )

    formatted = format_answer(result)

    assert "Deadline là 23:59." in formatted
    assert "[Thông báo](https://discord.com/channels/g/c/m)" in formatted


def test_support_ticket_contains_tracking_fields() -> None:
    formatted = format_support_ticket(
        author_mention="<@1>",
        question="Fix CUDA?",
        source_url="https://discord.com/channels/g/c/m",
        mentor_mention="<@2>",
        review_id="review-1",
        mentor_draft=MentorDraft(
            text="Bản nháp[1]",
            sources=(
                AnswerSource(
                    document_id="web:1",
                    title="PyTorch docs",
                    source_url="https://pytorch.org/docs/",
                ),
            ),
        ),
    )

    assert "Câu hỏi từ <@1>" in formatted
    assert "⬜ Chờ mentor duyệt" in formatted
    assert "<@2>" in formatted
    assert "!approve" in formatted
    assert "Bản nháp" in formatted
    assert "[1] [PyTorch docs](https://pytorch.org/docs/)" in formatted


def test_first_question_formatter_includes_onboarding_resources() -> None:
    result = ProcessingResult(
        kind=OutcomeKind.ESCALATED,
        mentor_mention="<@2>",
        onboarding_suggestions=(
            OnboardingSuggestion(
                title="Discord Developer Portal",
                target="https://discord.com/developers/applications",
            ),
            OnboardingSuggestion(
                title="Kênh mentor",
                target="<#3>",
            ),
        ),
    )

    formatted = format_escalation(result)

    assert "lần hỏi đầu tiên" in formatted
    assert (
        "[Discord Developer Portal]"
        "(https://discord.com/developers/applications)"
    ) in formatted
    assert "<#3>" in formatted


def test_forum_title_is_bounded() -> None:
    title = _forum_post_title("Một câu hỏi rất dài " * 20)

    assert title.startswith("Cần hỗ trợ:")
    assert len(title) <= 90


def test_review_command_parser_supports_approve_edit_and_reject() -> None:
    assert _parse_review_command("!approve") == (
        ReviewAction.APPROVE,
        "",
        "",
    )
    assert _parse_review_command("!send Bản mentor sửa") == (
        ReviewAction.EDIT_AND_SEND,
        "Bản mentor sửa",
        "",
    )
    assert _parse_review_command("!reject abc123") == (
        ReviewAction.REJECT,
        "",
        "abc123",
    )


def test_approved_answer_and_digest_formatting() -> None:
    approved = ReviewDecisionResult(
        kind=ReviewDecisionKind.READY_TO_SEND,
        message="ok",
        answer="Đã kiểm tra.",
    )
    digest = DigestResult(
        report_date="2026-07-30",
        pending_count=2,
        items=(
            DigestItem(
                question="Fix CUDA?",
                count=2,
                oldest_at=datetime.now(UTC),
                source_url="https://discord.com/channels/g/c/m",
                mentor_mention="<@&2>",
            ),
        ),
    )

    assert "Mentor đã duyệt" in format_approved_answer(approved)
    assert "lặp 2 lần" in format_digest(digest)
