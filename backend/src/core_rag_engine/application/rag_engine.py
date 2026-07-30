"""Core RAG orchestration independent of Discord and vendor SDKs."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import Sequence
from uuid import uuid4

from ..domain import (
    AnswerSource,
    Confidence,
    EscalationRecord,
    IngestDocument,
    MessageInput,
    OutcomeKind,
    ProcessingResult,
    RetrievedChunk,
)
from ..ports.outbound import (
    EmbeddingProviderPort,
    LearnerActivityPort,
    LLMProviderPort,
    MentorDraftProviderPort,
    MentorRouterPort,
    OnboardingAdvisorPort,
    SupportRepositoryPort,
    VectorStorePort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EngineConfig:
    question_mode: str = "question_mark"
    ignore_bot_messages: bool = True
    minimum_text_length: int = 3
    top_k: int = 5
    minimum_similarity: float = 0.45
    maximum_sources: int = 3
    onboarding_enabled: bool = True
    onboarding_suggestion_limit: int = 2
    mentor_research_enabled: bool = True


class CoreRAGEngine:
    """Application service implementing ingest, answer and escalation."""

    def __init__(
        self,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider: LLMProviderPort,
        mentor_router: MentorRouterPort,
        learner_activity: LearnerActivityPort,
        onboarding_advisor: OnboardingAdvisorPort,
        mentor_draft_provider: MentorDraftProviderPort,
        support_repository: SupportRepositoryPort,
        config: EngineConfig,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._mentor_router = mentor_router
        self._learner_activity = learner_activity
        self._onboarding_advisor = onboarding_advisor
        self._mentor_draft_provider = mentor_draft_provider
        self._support_repository = support_repository
        self._config = config

    def handle_message(self, message: MessageInput) -> ProcessingResult:
        content = message.content.strip()
        ignored_reason = self._ignored_reason(message, content)
        if ignored_reason:
            return ProcessingResult(kind=OutcomeKind.IGNORED, reason=ignored_reason)

        if not self._is_question(content):
            document = IngestDocument(
                document_id=f"discord:{message.message_id}",
                text=content,
                title=f"Discord message by {message.author_mention}",
                source_url=message.source_url,
                metadata={
                    "platform": "discord",
                    "author_id": message.author_id,
                    "channel_id": message.channel_id,
                    "created_at": message.created_at.isoformat(),
                },
            )
            self.ingest_documents([document])
            return ProcessingResult(kind=OutcomeKind.INGESTED)

        is_first_question = self._claim_first_question(message)
        result = self._answer_question(content)
        if result.kind is OutcomeKind.ESCALATED:
            result = self._register_escalation(message, result)
        if not is_first_question:
            return result
        return self._attach_onboarding(result, content)

    def ingest_documents(self, documents: Sequence[IngestDocument]) -> int:
        valid_documents = [doc for doc in documents if doc.text.strip()]
        if not valid_documents:
            return 0
        embeddings = self._embedding_provider.embed_documents(
            [doc.text for doc in valid_documents]
        )
        self._vector_store.upsert(valid_documents, embeddings)
        return len(valid_documents)

    def _answer_question(self, question: str) -> ProcessingResult:
        query_embedding = self._embedding_provider.embed_query(question)
        chunks = self._vector_store.query(query_embedding, self._config.top_k)
        eligible = [
            chunk
            for chunk in chunks
            if chunk.score >= self._config.minimum_similarity
        ]

        if not eligible:
            return self._escalate(
                routing_text=question,
                question=question,
                reason="retrieval_below_threshold",
                context=chunks,
            )

        try:
            generated = self._llm_provider.answer(question, eligible)
        except Exception:
            logger.exception("LLM provider failed; escalating safely")
            return self._escalate(
                routing_text=question,
                question=question,
                reason="llm_provider_error",
                context=eligible,
            )

        chunk_by_id = {chunk.document_id: chunk for chunk in eligible}
        cited_chunks = [
            chunk_by_id[source_id]
            for source_id in generated.source_ids
            if source_id in chunk_by_id
        ]

        if (
            generated.confidence is not Confidence.HIGH
            or not generated.answer.strip()
            or not cited_chunks
        ):
            routing_text = f"{question}\n{generated.answer}"
            return self._escalate(
                routing_text=routing_text,
                question=question,
                reason="llm_low_or_uncited",
                context=eligible,
            )

        sources = tuple(
            self._to_answer_source(chunk)
            for chunk in cited_chunks[: self._config.maximum_sources]
        )
        return ProcessingResult(
            kind=OutcomeKind.ANSWERED,
            answer=generated.answer.strip(),
            confidence=Confidence.HIGH,
            sources=sources,
        )

    def _escalate(
        self,
        *,
        routing_text: str,
        question: str,
        reason: str,
        context: Sequence[RetrievedChunk],
    ) -> ProcessingResult:
        mentor_draft = None
        if self._config.mentor_research_enabled:
            try:
                mentor_draft = self._mentor_draft_provider.draft(question, context)
            except Exception:
                logger.exception("Mentor draft provider failed; escalating without draft")
        return ProcessingResult(
            kind=OutcomeKind.ESCALATED,
            confidence=Confidence.LOW,
            mentor_mention=self._mentor_router.route(routing_text),
            mentor_draft=mentor_draft,
            reason=reason,
        )

    def _register_escalation(
        self,
        message: MessageInput,
        result: ProcessingResult,
    ) -> ProcessingResult:
        review_id = uuid4().hex[:12]
        record = EscalationRecord(
            review_id=review_id,
            question=message.content.strip(),
            author_id=message.author_id,
            author_mention=message.author_mention,
            original_channel_id=message.channel_id,
            original_message_id=message.message_id,
            source_url=message.source_url,
            mentor_mention=result.mentor_mention,
            created_at=message.created_at,
            draft=result.mentor_draft,
        )
        try:
            self._support_repository.create(record)
        except Exception:
            logger.exception("Could not persist escalation review")
            return replace(result, mentor_draft=None)
        return replace(result, review_id=review_id)

    def _claim_first_question(self, message: MessageInput) -> bool:
        if not self._config.onboarding_enabled:
            return False
        try:
            return self._learner_activity.claim_first_question(message)
        except Exception:
            logger.exception("Learner activity provider failed; skipping onboarding")
            return False

    def _attach_onboarding(
        self,
        result: ProcessingResult,
        question: str,
    ) -> ProcessingResult:
        try:
            suggestions = tuple(
                self._onboarding_advisor.suggest(
                    question,
                    self._config.onboarding_suggestion_limit,
                )
            )
        except Exception:
            logger.exception("Onboarding advisor failed; returning core result")
            return result
        if not suggestions:
            return result
        return replace(result, onboarding_suggestions=suggestions)

    def _ignored_reason(self, message: MessageInput, content: str) -> str:
        if self._config.ignore_bot_messages and message.is_bot:
            return "bot_message"
        if len(content) < self._config.minimum_text_length:
            return "too_short"
        if not re.search(r"\w", content, flags=re.UNICODE):
            return "emoji_or_symbol_only"
        return ""

    def _is_question(self, content: str) -> bool:
        if self._config.question_mode == "all_messages":
            return True
        return content.rstrip().endswith("?")

    @staticmethod
    def _to_answer_source(chunk: RetrievedChunk) -> AnswerSource:
        return AnswerSource(
            document_id=chunk.document_id,
            title=chunk.title,
            source_url=chunk.source_url,
        )
