from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence

import pytest

from app.ai import (
    AIProviderError,
    AnswerDecision,
    MalformedAIResponseError,
    SourceContext,
    SourceReference,
)
from app.models import KnowledgeSource, RetrievalHit
from app.qa import QAPipeline
from app.retrieval import RetrievalService


class StubAnswerGenerator:
    def __init__(
        self,
        decision: AnswerDecision | None = None,
        error: Exception | None = None,
    ) -> None:
        self.decision = decision
        self.error = error
        self.calls: list[tuple[str, tuple[SourceContext, ...]]] = []

    async def generate(
        self,
        question: str,
        sources: Sequence[SourceContext],
    ) -> AnswerDecision:
        self.calls.append((question, tuple(sources)))
        if self.error is not None:
            raise self.error
        assert self.decision is not None
        return self.decision


class IgnoringThresholdRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[int | None, float | None]] = []

    def search(
        self,
        query: str,
        sources: Iterable[KnowledgeSource],
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[RetrievalHit]:
        del query, sources
        self.calls.append((top_k, threshold))
        return self.hits


def source(
    key: str,
    content: str,
    *,
    official: bool = False,
    pinned: bool = False,
    important: bool = False,
) -> KnowledgeSource:
    return KnowledgeSource(
        source_key=key,
        title="#build-phase",
        content=content,
        source_url=f"https://discord.test/{key}",
        created_at="2026-08-01T09:00:00+07:00",
        official=official,
        is_pinned=pinned,
        is_important=important,
    )


def decision(
    *,
    source_ids: tuple[str, ...] = ("official-deadline",),
    confidence: str = "high",
    needs_human: bool = False,
) -> AnswerDecision:
    assert confidence in {"high", "low"}
    return AnswerDecision(
        answer="Deadline là 23:59 ngày 15/08.",
        confidence=confidence,
        sources=tuple(
            SourceReference(message_id=source_id, label="Thông báo") for source_id in source_ids
        ),
        topic="deadline",
        needs_human=needs_human,
    )


def test_answered_result_contains_only_backend_resolved_citations() -> None:
    trusted = source(
        "official-deadline",
        "Deadline Project 1 la 23:59 ngay 15/08.",
        official=True,
    )
    generator = StubAnswerGenerator(decision())
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=generator,
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Deadline Project 1 la khi nao?", [trusted]),
    )

    assert result.status == "answered"
    assert result.answer == "Deadline là 23:59 ngày 15/08."
    assert result.reason == "grounded_answer"
    assert result.cited_sources == (trusted,)
    assert result.hits[0].source is trusted
    assert generator.calls[0][1][0].message_id == trusted.source_key
    assert "https://" not in generator.calls[0][1][0].content


def test_pipeline_enforces_hard_similarity_gate_before_ai() -> None:
    irrelevant = source("weak", "Noi dung khong lien quan.")
    hit = RetrievalHit(
        source=irrelevant,
        similarity=0.19,
        ranking_score=0.9,
    )
    retriever = IgnoringThresholdRetriever([hit])
    generator = StubAnswerGenerator(decision(source_ids=("weak",)))
    pipeline = QAPipeline(
        retriever=retriever,
        answer_generator=generator,
        similarity_threshold=0.2,
    )

    result = asyncio.run(pipeline.ask("Deadline?", [irrelevant]))

    assert result.status == "escalate"
    assert result.reason == "no_relevant_sources"
    assert generator.calls == []
    assert retriever.calls == [(5, 0.2)]


def test_sensitive_question_uses_only_official_pinned_or_important_sources() -> None:
    community = source(
        "community-rumour",
        "Deadline Project 1 la ngay 14/08.",
    )
    official = source(
        "official-deadline",
        "Deadline Project 1 la ngay 15/08.",
        official=True,
    )
    generator = StubAnswerGenerator(decision())
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=generator,
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask(
            "Deadline Project 1 la khi nao?",
            [community, official],
        )
    )

    assert result.status == "answered"
    assert [hit.source.source_key for hit in result.hits] == ["official-deadline"]
    assert [item.message_id for item in generator.calls[0][1]] == ["official-deadline"]


def test_sensitive_question_without_trusted_source_escalates_without_ai() -> None:
    community = source(
        "community-rumour",
        "Rubric Project 1 co bon tieu chi.",
    )
    generator = StubAnswerGenerator(decision(source_ids=("community-rumour",)))
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=generator,
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Rubric Project 1 nhu the nao?", [community]),
    )

    assert result.status == "escalate"
    assert result.reason == "no_trusted_sources_for_sensitive_question"
    assert result.hits == ()
    assert generator.calls == []


def test_conflicting_trusted_sources_stop_before_ai() -> None:
    old = source(
        "old-deadline",
        "Deadline Project 1 la 23:59 ngay 15/08/2026.",
        official=True,
    )
    new = source(
        "new-deadline",
        "Deadline Project 1 la 23:59 ngay 16/08/2026.",
        pinned=True,
    )
    generator = StubAnswerGenerator(decision(source_ids=("new-deadline",)))
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=generator,
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Deadline Project 1 la khi nao?", [old, new]),
    )

    assert result.status == "conflict"
    assert result.reason == "conflicting_trusted_sources"
    assert {item.source_key for item in result.cited_sources} == {
        "old-deadline",
        "new-deadline",
    }
    assert generator.calls == []


@pytest.mark.parametrize(
    ("answer_decision", "reason"),
    [
        (decision(source_ids=("made-up-source",)), "invalid_source_references"),
        (decision(source_ids=()), "missing_source_references"),
        (
            decision(confidence="low", needs_human=True),
            "low_confidence",
        ),
        (decision(needs_human=True), "human_review_requested"),
    ],
)
def test_unsafe_ai_decisions_escalate(
    answer_decision: AnswerDecision,
    reason: str,
) -> None:
    trusted = source(
        "official-deadline",
        "Deadline Project 1 la ngay 15/08.",
        official=True,
    )
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=StubAnswerGenerator(answer_decision),
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Deadline Project 1 la khi nao?", [trusted]),
    )

    assert result.status == "escalate"
    assert result.answer is None
    assert result.reason == reason
    if reason == "invalid_source_references":
        assert result.cited_sources == ()


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            AIProviderError("safe provider failure"),
            "ai_provider_unavailable",
        ),
        (
            MalformedAIResponseError("safe malformed response"),
            "malformed_ai_response",
        ),
    ],
)
def test_ai_failures_return_typed_unavailable_result(
    error: Exception,
    reason: str,
) -> None:
    trusted = source(
        "official-deadline",
        "Deadline Project 1 la ngay 15/08.",
        official=True,
    )
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=StubAnswerGenerator(error=error),
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Deadline Project 1 la khi nao?", [trusted]),
    )

    assert result.status == "ai_unavailable"
    assert result.answer is None
    assert result.reason == reason
    assert result.hits[0].source is trusted


def test_missing_ai_configuration_escalates_without_guessing() -> None:
    trusted = source(
        "official-deadline",
        "Deadline Project 1 la ngay 15/08.",
        official=True,
    )
    pipeline = QAPipeline(
        retriever=RetrievalService(threshold=0.2),
        answer_generator=None,
        similarity_threshold=0.2,
    )

    result = asyncio.run(
        pipeline.ask("Deadline Project 1 la khi nao?", [trusted]),
    )

    assert result.status == "ai_unavailable"
    assert result.answer is None
    assert result.reason == "ai_not_configured"
