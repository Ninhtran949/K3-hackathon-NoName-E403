"""Technology-independent domain models for the RAG engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"


class OutcomeKind(StrEnum):
    IGNORED = "ignored"
    INGESTED = "ingested"
    ANSWERED = "answered"
    ESCALATED = "escalated"


MetadataValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class MessageInput:
    message_id: str
    content: str
    author_id: str
    author_mention: str
    channel_id: str
    source_url: str
    created_at: datetime
    is_bot: bool = False


@dataclass(frozen=True, slots=True)
class IngestDocument:
    document_id: str
    text: str
    title: str
    source_url: str = ""
    metadata: Mapping[str, MetadataValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_id: str
    text: str
    title: str
    source_url: str
    score: float
    metadata: Mapping[str, MetadataValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMAnswer:
    answer: str
    confidence: Confidence
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerSource:
    document_id: str
    title: str
    source_url: str


@dataclass(frozen=True, slots=True)
class OnboardingSuggestion:
    title: str
    target: str


@dataclass(frozen=True, slots=True)
class MentorDraft:
    text: str
    sources: tuple[AnswerSource, ...] = ()
    caveats: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EscalationRecord:
    review_id: str
    question: str
    author_id: str
    author_mention: str
    original_channel_id: str
    original_message_id: str
    source_url: str
    mentor_mention: str
    created_at: datetime
    draft: MentorDraft | None = None
    support_context_id: str = ""


class ReviewAction(StrEnum):
    APPROVE = "approve"
    EDIT_AND_SEND = "edit_and_send"
    REJECT = "reject"


class ReviewDecisionKind(StrEnum):
    READY_TO_SEND = "ready_to_send"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    INVALID = "invalid"
    ALREADY_RESOLVED = "already_resolved"


@dataclass(frozen=True, slots=True)
class MentorDecisionInput:
    support_context_id: str
    reviewer_id: str
    reviewer_role_ids: tuple[str, ...]
    can_moderate: bool
    action: ReviewAction
    edited_answer: str = ""
    review_id: str = ""


@dataclass(frozen=True, slots=True)
class ReviewDecisionResult:
    kind: ReviewDecisionKind
    message: str
    review_id: str = ""
    answer: str = ""
    original_channel_id: str = ""
    original_message_id: str = ""
    sources: tuple[AnswerSource, ...] = ()


@dataclass(frozen=True, slots=True)
class DigestItem:
    question: str
    count: int
    oldest_at: datetime
    source_url: str
    mentor_mention: str


@dataclass(frozen=True, slots=True)
class DigestResult:
    report_date: str
    pending_count: int
    items: tuple[DigestItem, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    kind: OutcomeKind
    answer: str = ""
    confidence: Confidence = Confidence.LOW
    sources: tuple[AnswerSource, ...] = ()
    onboarding_suggestions: tuple[OnboardingSuggestion, ...] = ()
    mentor_mention: str = ""
    review_id: str = ""
    mentor_draft: MentorDraft | None = None
    reason: str = ""
