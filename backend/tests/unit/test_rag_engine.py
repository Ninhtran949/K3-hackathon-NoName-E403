from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from src.core_rag_engine.application import CoreRAGEngine, EngineConfig
from src.core_rag_engine.domain import (
    Confidence,
    EscalationRecord,
    IngestDocument,
    LLMAnswer,
    MessageInput,
    MentorDraft,
    OnboardingSuggestion,
    OutcomeKind,
    RetrievedChunk,
)


class FakeEmbeddingProvider:
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self.chunks = chunks or []
        self.upserted: list[IngestDocument] = []

    def upsert(self, documents, embeddings) -> None:
        self.upserted.extend(documents)

    def query(self, query_embedding, top_k: int) -> list[RetrievedChunk]:
        return self.chunks[:top_k]


class FakeLLM:
    def __init__(self, answer: LLMAnswer) -> None:
        self.answer_value = answer
        self.calls = 0

    def answer(self, question, context) -> LLMAnswer:
        self.calls += 1
        return self.answer_value


class FakeRouter:
    def route(self, text: str) -> str:
        return "<@123>"


class FakeLearnerActivity:
    def __init__(self) -> None:
        self.seen: set[tuple[str, str]] = set()

    def claim_first_question(self, message: MessageInput) -> bool:
        key = (message.author_id, message.channel_id)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


class FakeOnboardingAdvisor:
    def suggest(self, question: str, limit: int):
        return (
            OnboardingSuggestion(
                title="Kênh bắt đầu",
                target="<#10>",
            ),
        )[:limit]


class FakeMentorDraftProvider:
    def __init__(self) -> None:
        self.calls = 0

    def draft(self, question, context) -> MentorDraft:
        self.calls += 1
        return MentorDraft(text="Bản nháp cho mentor")


class FakeSupportRepository:
    def __init__(self) -> None:
        self.records: list[EscalationRecord] = []

    def create(self, record: EscalationRecord) -> None:
        self.records.append(record)


def make_message(content: str, *, is_bot: bool = False) -> MessageInput:
    return MessageInput(
        message_id="m1",
        content=content,
        author_id="u1",
        author_mention="<@u1>",
        channel_id="c1",
        source_url="https://discord.com/channels/g/c/m1",
        created_at=datetime.now(UTC),
        is_bot=is_bot,
    )


def make_engine(
    *,
    chunks: list[RetrievedChunk] | None = None,
    llm_answer: LLMAnswer | None = None,
) -> tuple[CoreRAGEngine, FakeVectorStore, FakeLLM]:
    store = FakeVectorStore(chunks)
    llm = FakeLLM(
        llm_answer
        or LLMAnswer(
            answer="Câu trả lời",
            confidence=Confidence.HIGH,
            source_ids=("doc-1",),
        )
    )
    engine = CoreRAGEngine(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=store,
        llm_provider=llm,
        mentor_router=FakeRouter(),
        learner_activity=FakeLearnerActivity(),
        onboarding_advisor=FakeOnboardingAdvisor(),
        mentor_draft_provider=FakeMentorDraftProvider(),
        support_repository=FakeSupportRepository(),
        config=EngineConfig(minimum_similarity=0.45),
    )
    return engine, store, llm


def test_non_question_message_is_ingested() -> None:
    engine, store, _ = make_engine()

    result = engine.handle_message(make_message("Deadline là 23:59 ngày mai."))

    assert result.kind is OutcomeKind.INGESTED
    assert store.upserted[0].source_url.endswith("/m1")


def test_grounded_high_confidence_answer_includes_source() -> None:
    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            text="Deadline là 23:59.",
            title="Thông báo deadline",
            source_url="https://discord.com/channels/g/c/source",
            score=0.9,
        )
    ]
    engine, _, llm = make_engine(chunks=chunks)

    result = engine.handle_message(make_message("Deadline là khi nào?"))

    assert result.kind is OutcomeKind.ANSWERED
    assert result.confidence is Confidence.HIGH
    assert result.sources[0].document_id == "doc-1"
    assert llm.calls == 1


def test_only_first_question_in_channel_gets_onboarding_suggestions() -> None:
    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            text="Deadline là 23:59.",
            title="Thông báo deadline",
            source_url="https://discord.com/channels/g/c/source",
            score=0.9,
        )
    ]
    engine, _, _ = make_engine(chunks=chunks)

    first = engine.handle_message(make_message("Deadline là khi nào?"))
    second = engine.handle_message(make_message("Deadline có đổi không?"))

    assert first.onboarding_suggestions[0].target == "<#10>"
    assert second.onboarding_suggestions == ()


def test_low_retrieval_escalates_without_calling_llm() -> None:
    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            text="Không liên quan",
            title="Nguồn",
            source_url="",
            score=0.2,
        )
    ]
    engine, _, llm = make_engine(chunks=chunks)

    result = engine.handle_message(make_message("Fix CUDA thế nào?"))

    assert result.kind is OutcomeKind.ESCALATED
    assert result.mentor_mention == "<@123>"
    assert result.reason == "retrieval_below_threshold"
    assert llm.calls == 0
    assert result.review_id
    assert result.mentor_draft


def test_uncited_high_confidence_answer_is_escalated() -> None:
    chunks = [
        RetrievedChunk(
            document_id="doc-1",
            text="Có dữ liệu",
            title="Nguồn",
            source_url="",
            score=0.9,
        )
    ]
    engine, _, _ = make_engine(
        chunks=chunks,
        llm_answer=LLMAnswer(
            answer="Câu trả lời không có citation",
            confidence=Confidence.HIGH,
            source_ids=(),
        ),
    )

    result = engine.handle_message(make_message("Câu hỏi?"))

    assert result.kind is OutcomeKind.ESCALATED
    assert result.reason == "llm_low_or_uncited"


def test_bot_and_emoji_only_messages_are_ignored() -> None:
    engine, _, _ = make_engine()

    assert engine.handle_message(make_message("Bot text", is_bot=True)).kind is (
        OutcomeKind.IGNORED
    )
    assert engine.handle_message(make_message("🔥🔥🔥")).kind is OutcomeKind.IGNORED
