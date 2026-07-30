from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """A persisted piece of knowledge that may be shown as an answer source.

    IDs stay optional so the same model works for static seed documents and
    Discord messages. Timestamps are ISO-8601 strings at this boundary; parsing
    them is the responsibility of the persistence/integration layer.
    """

    id: int | None = None
    source_key: str = ""
    source_type: str = "discord_message"
    guild_id: int | None = None
    channel_id: int | None = None
    message_id: int | None = None
    author_id: int | None = None
    author_name: str = ""
    author_role_ids: frozenset[int] = field(default_factory=frozenset)
    title: str = ""
    content: str = ""
    source_url: str = ""
    created_at: str = ""
    edited_at: str | None = None
    is_pinned: bool = False
    is_important: bool = False
    priority: int = 0
    active: bool = True
    official: bool = False

    def __post_init__(self) -> None:
        # Be forgiving at integration boundaries while retaining an immutable
        # value object for deterministic retrieval and tests.
        if not isinstance(self.author_role_ids, frozenset):
            object.__setattr__(self, "author_role_ids", frozenset(self.author_role_ids))

    @property
    def url(self) -> str:
        """Compatibility/readability alias used by response formatting."""

        return self.source_url

    @property
    def pinned(self) -> bool:
        return self.is_pinned

    @property
    def important(self) -> bool:
        return self.is_important


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """A source together with relevance and final ranking information."""

    source: KnowledgeSource
    similarity: float
    ranking_score: float
    matched_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.similarity <= 1.0:
            raise ValueError("similarity must be between 0 and 1")
        if not 0.0 <= self.ranking_score <= 1.0:
            raise ValueError("ranking_score must be between 0 and 1")

    @property
    def score(self) -> float:
        """Alias for callers that use the conventional retrieval score name."""

        return self.similarity

    @property
    def rank_score(self) -> float:
        return self.ranking_score
