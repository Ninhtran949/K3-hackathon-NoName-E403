from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from app.ai import (
    AIConfigurationError,
    AIProviderError,
    AnswerDecision,
    AnswerGenerationError,
    AnswerGenerator,
    MalformedAIResponseError,
    SourceContext,
)
from app.models import KnowledgeSource, RetrievalHit
from app.retrieval import (
    RetrievalService,
    find_temporal_conflicts,
    is_sensitive_fact_question,
)

QAStatus = Literal["answered", "escalate", "conflict", "ai_unavailable"]


class Retriever(Protocol):
    def search(
        self,
        query: str,
        sources: Iterable[KnowledgeSource],
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[RetrievalHit]:
        """Return ranked retrieval candidates."""


@dataclass(frozen=True, slots=True)
class QAResult:
    status: QAStatus
    answer: str | None
    topic: str
    reason: str
    cited_sources: tuple[KnowledgeSource, ...]
    hits: tuple[RetrievalHit, ...]


class QAPipeline:
    """Pure retrieval-to-answer pipeline with conservative safety gates."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        answer_generator: AnswerGenerator | None,
        similarity_threshold: float = 0.25,
        top_k: int = 5,
        conflict_min_priority: int = 2,
        max_source_chars: int = 12_000,
    ) -> None:
        RetrievalService._validate_unit_interval(
            similarity_threshold,
            "similarity_threshold",
        )
        RetrievalService._validate_top_k(top_k)
        if (
            isinstance(conflict_min_priority, bool)
            or not isinstance(conflict_min_priority, int)
            or conflict_min_priority < 0
        ):
            raise ValueError("conflict_min_priority must be a non-negative integer")
        if (
            isinstance(max_source_chars, bool)
            or not isinstance(max_source_chars, int)
            or max_source_chars <= 0
        ):
            raise ValueError("max_source_chars must be a positive integer")

        self.retriever = retriever
        self.answer_generator = answer_generator
        self.similarity_threshold = float(similarity_threshold)
        self.top_k = top_k
        self.conflict_min_priority = conflict_min_priority
        self.max_source_chars = max_source_chars

    async def ask(
        self,
        question: str,
        sources: Iterable[KnowledgeSource],
    ) -> QAResult:
        normalized_question = _question(question)
        retrieved = self.retriever.search(
            normalized_question,
            sources,
            top_k=self.top_k,
            threshold=self.similarity_threshold,
        )

        # Enforce the relevance threshold here even when an alternate Retriever
        # implementation ignores the requested threshold.
        gated_hits = tuple(
            hit
            for hit in retrieved
            if hit.similarity >= self.similarity_threshold
            and _source_reference_id(hit.source) is not None
        )
        if not gated_hits:
            return _result(
                status="escalate",
                reason="no_relevant_sources",
                hits=(),
            )

        if is_sensitive_fact_question(normalized_question):
            gated_hits = tuple(hit for hit in gated_hits if _is_explicitly_trusted(hit.source))
            if not gated_hits:
                return _result(
                    status="escalate",
                    reason="no_trusted_sources_for_sensitive_question",
                    hits=(),
                )

        conflicts = find_temporal_conflicts(
            normalized_question,
            gated_hits,
            min_similarity=self.similarity_threshold,
            min_priority=self.conflict_min_priority,
        )
        if conflicts:
            conflict_keys = {conflict.left.source.source_key for conflict in conflicts} | {
                conflict.right.source.source_key for conflict in conflicts
            }
            cited_sources = tuple(
                hit.source for hit in gated_hits if hit.source.source_key in conflict_keys
            )
            return _result(
                status="conflict",
                reason="conflicting_trusted_sources",
                cited_sources=cited_sources,
                hits=gated_hits,
            )

        contexts, sources_by_reference = self._build_contexts(gated_hits)
        if not contexts:
            return _result(
                status="escalate",
                reason="no_citable_sources",
                hits=gated_hits,
            )

        if self.answer_generator is None:
            return _result(
                status="ai_unavailable",
                reason="ai_not_configured",
                hits=gated_hits,
            )

        try:
            decision = await self.answer_generator.generate(
                normalized_question,
                contexts,
            )
        except MalformedAIResponseError:
            return _result(
                status="ai_unavailable",
                reason="malformed_ai_response",
                hits=gated_hits,
            )
        except (AIProviderError, AIConfigurationError):
            return _result(
                status="ai_unavailable",
                reason="ai_provider_unavailable",
                hits=gated_hits,
            )
        except AnswerGenerationError:
            return _result(
                status="ai_unavailable",
                reason="ai_generation_failed",
                hits=gated_hits,
            )

        return self._validate_decision(
            decision,
            sources_by_reference=sources_by_reference,
            hits=gated_hits,
        )

    async def answer(
        self,
        question: str,
        sources: Sequence[KnowledgeSource],
    ) -> QAResult:
        """Readable alias for integrations which call the pipeline an answerer."""

        return await self.ask(question, sources)

    def _build_contexts(
        self,
        hits: Sequence[RetrievalHit],
    ) -> tuple[tuple[SourceContext, ...], dict[str, KnowledgeSource]]:
        contexts: list[SourceContext] = []
        sources_by_reference: dict[str, KnowledgeSource] = {}

        for hit in hits:
            source = hit.source
            reference_id = _source_reference_id(source)
            if reference_id is None or reference_id in sources_by_reference:
                continue

            content = "\n".join(
                part.strip() for part in (source.title, source.content) if part.strip()
            )
            if not content:
                continue
            content = content[: self.max_source_chars]

            label = (source.title.strip() or source.source_type or "Knowledge source")[:200]
            channel_name = (source.title.strip() or "unknown")[:100]
            contexts.append(
                SourceContext(
                    message_id=reference_id,
                    content=content,
                    label=label,
                    author_role=_authority_label(source),
                    channel_name=channel_name,
                    timestamp=(source.created_at.strip() or "unknown")[:100],
                )
            )
            sources_by_reference[reference_id] = source

        return tuple(contexts), sources_by_reference

    @staticmethod
    def _validate_decision(
        decision: AnswerDecision,
        *,
        sources_by_reference: dict[str, KnowledgeSource],
        hits: tuple[RetrievalHit, ...],
    ) -> QAResult:
        candidate_ids = decision.source_ids
        if not candidate_ids:
            return _result(
                status="escalate",
                topic=decision.topic,
                reason="missing_source_references",
                hits=hits,
            )

        if any(source_id not in sources_by_reference for source_id in candidate_ids):
            return _result(
                status="escalate",
                topic=decision.topic,
                reason="invalid_source_references",
                hits=hits,
            )

        cited_sources = tuple(sources_by_reference[source_id] for source_id in candidate_ids)
        if decision.confidence != "high":
            return _result(
                status="escalate",
                topic=decision.topic,
                reason="low_confidence",
                cited_sources=cited_sources,
                hits=hits,
            )
        if decision.needs_human:
            return _result(
                status="escalate",
                topic=decision.topic,
                reason="human_review_requested",
                cited_sources=cited_sources,
                hits=hits,
            )

        return _result(
            status="answered",
            answer=decision.answer,
            topic=decision.topic,
            reason="grounded_answer",
            cited_sources=cited_sources,
            hits=hits,
        )


def _question(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("question must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("question must not be empty")
    return normalized


def _source_reference_id(source: KnowledgeSource) -> str | None:
    reference_id = source.source_key.strip()
    if not reference_id or len(reference_id) > 128:
        return None
    allowed = all(
        character.isascii() and (character.isalnum() or character in {"_", ".", ":", "-"})
        for character in reference_id
    )
    return reference_id if allowed else None


def _is_explicitly_trusted(source: KnowledgeSource) -> bool:
    return source.official or source.is_pinned or source.is_important


def _authority_label(source: KnowledgeSource) -> str:
    labels: list[str] = []
    if source.official:
        labels.append("official")
    if source.is_pinned:
        labels.append("pinned")
    if source.is_important:
        labels.append("important")
    return ",".join(labels) or "community"


def _result(
    *,
    status: QAStatus,
    reason: str,
    answer: str | None = None,
    topic: str = "",
    cited_sources: Sequence[KnowledgeSource] = (),
    hits: Sequence[RetrievalHit] = (),
) -> QAResult:
    return QAResult(
        status=status,
        answer=answer,
        topic=topic,
        reason=reason,
        cited_sources=tuple(cited_sources),
        hits=tuple(hits),
    )
