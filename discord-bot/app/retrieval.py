from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations

from app.models import KnowledgeSource, RetrievalHit

# These are deliberately limited to grammatical/query filler words. Domain
# words such as "điểm", "lịch", "bài", and "thông báo" carry retrieval value.
_VIETNAMESE_STOPWORDS = frozenset(
    {
        "a",
        "ay",
        "bi",
        "ban",
        "bang",
        "cho",
        "co",
        "cua",
        "cung",
        "da",
        "dang",
        "day",
        "de",
        "den",
        "do",
        "duoc",
        "gi",
        "hay",
        "hoi",
        "khi",
        "khong",
        "kia",
        "la",
        "lam",
        "luc",
        "ma",
        "minh",
        "mot",
        "nao",
        "nay",
        "nhu",
        "nhung",
        "o",
        "rang",
        "sao",
        "se",
        "thi",
        "the",
        "theo",
        "toi",
        "tren",
        "tu",
        "va",
        "ve",
        "vi",
        "voi",
        "xin",
    }
)

_PHRASE_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bhan\s+chot\b"), " deadline "),
    (re.compile(r"\bhan\s+nop\b"), " deadline "),
    (re.compile(r"\bngay\s+het\s+han\b"), " deadline "),
    (re.compile(r"\bquy\s+dinh\b"), " rule "),
    (re.compile(r"\bnoi\s+quy\b"), " rule "),
    (re.compile(r"\bquy\s+che\b"), " rule "),
    (re.compile(r"\btieu\s+chi\s+cham(?:\s+bai)?\b"), " rubric "),
    (re.compile(r"\bthang\s+diem\b"), " score "),
    (re.compile(r"\bdiem\s+so\b"), " score "),
)

_SENSITIVE_TOKENS = frozenset(
    {
        "deadline",
        "diem",
        "rubric",
        "rule",
        "score",
    }
)
_SENSITIVE_PHRASES = (
    "lich hoc",
    "lich su kien",
    "bat buoc",
    "huy su kien",
    "huy workshop",
    "thay doi lich",
    "thay doi deadline",
)

# Words which describe the fact rather than the subject of that fact. Removing
# them leaves anchors such as ("project", "1") or ("capstone",).
_CONFLICT_GENERIC_TOKENS = _SENSITIVE_TOKENS | frozenset(
    {
        "bai",
        "cham",
        "gio",
        "han",
        "lich",
        "ngay",
        "nop",
        "thoi",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DATE_DMY_RE = re.compile(
    r"(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])"
    r"\s*[/-]\s*(?P<month>0?[1-9]|1[0-2])"
    r"(?:\s*[/-]\s*(?P<year>(?:19|20)?\d{2}))?(?!\d)"
)
_DATE_YMD_RE = re.compile(
    r"(?<!\d)(?P<year>(?:19|20)\d{2})"
    r"\s*[/-]\s*(?P<month>0?[1-9]|1[0-2])"
    r"\s*[/-]\s*(?P<day>0?[1-9]|[12]\d|3[01])(?!\d)"
)
_DATE_DOT_DMY_RE = re.compile(
    r"(?<![\d.])(?P<day>0?[1-9]|[12]\d|3[01])"
    r"\s*\.\s*(?P<month>0?[1-9]|1[0-2])"
    r"\s*\.\s*(?P<year>(?:19|20)?\d{2})(?![\d.])"
)
_DATE_DOT_YMD_RE = re.compile(
    r"(?<![\d.])(?P<year>(?:19|20)\d{2})"
    r"\s*\.\s*(?P<month>0?[1-9]|1[0-2])"
    r"\s*\.\s*(?P<day>0?[1-9]|[12]\d|3[01])(?![\d.])"
)
_DATE_WORD_RE = re.compile(
    r"\bngay\s+(?P<day>0?[1-9]|[12]\d|3[01])"
    r"\s+thang\s+(?P<month>0?[1-9]|1[0-2])"
    r"(?:\s+nam\s+(?P<year>(?:19|20)?\d{2}))?\b"
)
_TIME_RE = re.compile(
    r"(?<!\d)(?P<hour>[01]?\d|2[0-3])"
    r"\s*(?::|h|gio)\s*(?P<minute>[0-5]\d)(?!\d)"
)
_TIME_HOUR_ONLY_RE = re.compile(r"(?<!\d)(?P<hour>[01]?\d|2[0-3])\s*(?:h|gio)\b")


def normalize_text(text: str) -> str:
    """Normalize Vietnamese text for matching, including ``đ`` and accents."""

    value = text.casefold().replace("đ", "d")
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.split())


def _canonicalize_phrases(text: str) -> str:
    normalized = normalize_text(text)
    for pattern, replacement in _PHRASE_ALIASES:
        normalized = pattern.sub(replacement, normalized)
    return " ".join(normalized.split())


def tokenize(text: str, *, remove_stopwords: bool = True) -> list[str]:
    """Return deterministic accent-insensitive Vietnamese lexical tokens."""

    tokens = _TOKEN_RE.findall(_canonicalize_phrases(text))
    if remove_stopwords:
        tokens = [token for token in tokens if token not in _VIETNAMESE_STOPWORDS]
    return tokens


def lexical_similarity(query: str, document: str) -> float:
    """Compute query-oriented lexical relevance in the closed range 0..1.

    The main signal is query-token coverage so concise questions can match a
    longer announcement. Sørensen-Dice overlap prevents a single common token
    from receiving an overly generous score.
    """

    query_tokens = set(tokenize(query))
    document_tokens = set(tokenize(document))
    if not query_tokens or not document_tokens:
        return 0.0

    overlap_count = len(query_tokens & document_tokens)
    if overlap_count == 0:
        return 0.0

    coverage = overlap_count / len(query_tokens)
    dice = (2.0 * overlap_count) / (len(query_tokens) + len(document_tokens))
    score = (0.75 * coverage) + (0.25 * dice)
    return round(min(1.0, max(0.0, score)), 12)


def is_sensitive_fact(text: str) -> bool:
    """Whether text concerns a fact the bot must not guess."""

    normalized = normalize_text(text)
    return bool(set(tokenize(text)) & _SENSITIVE_TOKENS) or any(
        phrase in normalized for phrase in _SENSITIVE_PHRASES
    )


def is_sensitive_fact_question(text: str) -> bool:
    """Readable alias for Q&A call sites."""

    return is_sensitive_fact(text)


def _source_authority(source: KnowledgeSource) -> float:
    """Return a bounded authority signal used only as a ranking bonus."""

    priority_signal = min(max(source.priority, 0), 10) / 10.0
    authority = (
        (0.45 if source.official else 0.0)
        + (0.20 if source.is_pinned else 0.0)
        + (0.20 if source.is_important else 0.0)
        + (0.15 * priority_signal)
    )
    return min(1.0, authority)


class RetrievalService:
    """Pure lexical retrieval over caller-authorized sources."""

    def __init__(
        self,
        *,
        top_k: int = 5,
        threshold: float = 0.25,
        authority_bonus: float = 0.08,
    ) -> None:
        self._validate_top_k(top_k)
        self._validate_unit_interval(threshold, "threshold")
        self._validate_unit_interval(authority_bonus, "authority_bonus")
        self.top_k = top_k
        self.threshold = threshold
        self.authority_bonus = authority_bonus

    def search(
        self,
        query: str,
        sources: Iterable[KnowledgeSource],
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[RetrievalHit]:
        """Rank active sources, filter by lexical relevance, then take top-k.

        Filtering happens *before* the authority bonus is added. Consequently,
        an official but unrelated message can never cross the relevance gate
        merely because it has a high priority.
        """

        effective_top_k = self.top_k if top_k is None else top_k
        effective_threshold = self.threshold if threshold is None else threshold
        self._validate_top_k(effective_top_k)
        self._validate_unit_interval(effective_threshold, "threshold")

        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []

        hits: list[RetrievalHit] = []
        for source in sources:
            if not source.active:
                continue

            searchable_text = "\n".join(part for part in (source.title, source.content) if part)
            similarity = lexical_similarity(query, searchable_text)

            # Zero-overlap sources remain irrelevant even when a caller elects
            # to use a zero threshold.
            if similarity == 0.0 or similarity < effective_threshold:
                continue

            authority = _source_authority(source)
            ranking_score = min(1.0, similarity + (self.authority_bonus * authority))
            source_tokens = set(tokenize(searchable_text))
            matched_tokens = tuple(sorted(query_tokens & source_tokens))
            hits.append(
                RetrievalHit(
                    source=source,
                    similarity=similarity,
                    ranking_score=round(ranking_score, 12),
                    matched_tokens=matched_tokens,
                )
            )

        hits.sort(
            key=lambda hit: (
                -hit.ranking_score,
                -hit.similarity,
                -_source_authority(hit.source),
                hit.source.source_key,
                hit.source.id if hit.source.id is not None else -1,
            )
        )
        return hits[:effective_top_k]

    def rank(
        self,
        query: str,
        sources: Iterable[KnowledgeSource],
        *,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[RetrievalHit]:
        """Alias emphasizing that results are deterministically ordered."""

        return self.search(query, sources, top_k=top_k, threshold=threshold)

    @staticmethod
    def _validate_top_k(value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("top_k must be a positive integer")

    @staticmethod
    def _validate_unit_interval(value: float, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TemporalConflict:
    """Two trusted sources asserting different atomic date/time values."""

    left: RetrievalHit
    right: RetrievalHit
    fact_kind: str
    left_value: str
    right_value: str


@dataclass(frozen=True, slots=True)
class _TemporalFacts:
    dates: frozenset[tuple[int, int, int | None]]
    times: frozenset[int]


def _parse_year(value: str | None) -> int | None:
    if value is None:
        return None
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def _extract_temporal_facts(text: str) -> _TemporalFacts:
    normalized = normalize_text(text)
    dates: set[tuple[int, int, int | None]] = set()
    occupied_spans: list[tuple[int, int]] = []

    for pattern in (
        _DATE_YMD_RE,
        _DATE_DMY_RE,
        _DATE_DOT_YMD_RE,
        _DATE_DOT_DMY_RE,
        _DATE_WORD_RE,
    ):
        for match in pattern.finditer(normalized):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in occupied_spans):
                continue
            if pattern is _DATE_DMY_RE and match.groupdict().get("year") is None:
                context = normalized[max(0, span[0] - 40) : min(len(normalized), span[1] + 10)]
                score_context = {"cham", "diem", "rubric", "score"} & set(tokenize(context))
                temporal_context = {"deadline", "han", "lich", "ngay"} & set(tokenize(context))
                if score_context and not temporal_context:
                    # Values such as "8/10 điểm" are scores, not dates.
                    continue
            dates.add(
                (
                    int(match.group("day")),
                    int(match.group("month")),
                    _parse_year(match.groupdict().get("year")),
                )
            )
            occupied_spans.append(span)

    times: set[int] = set()
    full_time_spans: list[tuple[int, int]] = []
    for match in _TIME_RE.finditer(normalized):
        times.add((int(match.group("hour")) * 60) + int(match.group("minute")))
        full_time_spans.append(match.span())

    for match in _TIME_HOUR_ONLY_RE.finditer(normalized):
        span = match.span()
        if any(span[0] < end and start < span[1] for start, end in full_time_spans):
            continue
        times.add(int(match.group("hour")) * 60)

    return _TemporalFacts(frozenset(dates), frozenset(times))


def _is_high_trust(source: KnowledgeSource, min_priority: int) -> bool:
    return (
        source.official
        or source.is_pinned
        or source.is_important
        or source.priority >= min_priority
    )


def _date_values_conflict(
    left: tuple[int, int, int | None],
    right: tuple[int, int, int | None],
) -> bool:
    left_day, left_month, left_year = left
    right_day, right_month, right_year = right
    if (left_day, left_month) != (right_day, right_month):
        return True
    return left_year is not None and right_year is not None and left_year != right_year


def _format_date(value: tuple[int, int, int | None]) -> str:
    day, month, year = value
    suffix = f"/{year:04d}" if year is not None else ""
    return f"{day:02d}/{month:02d}{suffix}"


def _format_time(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def find_temporal_conflicts(
    query: str,
    hits: Sequence[RetrievalHit],
    *,
    min_similarity: float = 0.25,
    min_priority: int = 2,
) -> list[TemporalConflict]:
    """Find conservative conflicts between relevant, high-trust sources.

    A conflict is emitted only when:
    - the question concerns a sensitive fact;
    - it names a subject anchor (for example ``project 1``);
    - both sources are relevant, trusted, and mention that anchor; and
    - each source states exactly one value of the compared date/time kind.

    The singleton rule intentionally avoids guessing when a message says a
    deadline was moved "from X to Y" or contains a time range.
    """

    RetrievalService._validate_unit_interval(min_similarity, "min_similarity")
    if not is_sensitive_fact(query):
        return []

    anchor_tokens = set(tokenize(query)) - _CONFLICT_GENERIC_TOKENS
    if not anchor_tokens:
        return []

    candidates: list[tuple[RetrievalHit, _TemporalFacts]] = []
    for hit in hits:
        if hit.similarity < min_similarity or not _is_high_trust(hit.source, min_priority):
            continue

        source_text = "\n".join(part for part in (hit.source.title, hit.source.content) if part)
        if not anchor_tokens.issubset(set(tokenize(source_text))):
            continue

        facts = _extract_temporal_facts(source_text)
        if facts.dates or facts.times:
            candidates.append((hit, facts))

    conflicts: list[TemporalConflict] = []
    for (left_hit, left_facts), (right_hit, right_facts) in combinations(candidates, 2):
        if left_hit.source.source_key == right_hit.source.source_key:
            continue

        if len(left_facts.dates) == len(right_facts.dates) == 1:
            left_date = next(iter(left_facts.dates))
            right_date = next(iter(right_facts.dates))
            if _date_values_conflict(left_date, right_date):
                conflicts.append(
                    TemporalConflict(
                        left=left_hit,
                        right=right_hit,
                        fact_kind="date",
                        left_value=_format_date(left_date),
                        right_value=_format_date(right_date),
                    )
                )

        if len(left_facts.times) == len(right_facts.times) == 1:
            left_time = next(iter(left_facts.times))
            right_time = next(iter(right_facts.times))
            if left_time != right_time:
                conflicts.append(
                    TemporalConflict(
                        left=left_hit,
                        right=right_hit,
                        fact_kind="time",
                        left_value=_format_time(left_time),
                        right_value=_format_time(right_time),
                    )
                )

    conflicts.sort(
        key=lambda conflict: (
            conflict.left.source.source_key,
            conflict.right.source.source_key,
            conflict.fact_kind,
        )
    )
    return conflicts


def has_conflicting_sensitive_facts(
    query: str,
    hits: Sequence[RetrievalHit],
    *,
    min_similarity: float = 0.25,
    min_priority: int = 2,
) -> bool:
    return bool(
        find_temporal_conflicts(
            query,
            hits,
            min_similarity=min_similarity,
            min_priority=min_priority,
        )
    )


def detect_conflicts(
    query: str,
    hits: Sequence[RetrievalHit],
    *,
    min_similarity: float = 0.25,
    min_priority: int = 2,
) -> bool:
    """Short boolean alias suitable for the Q&A decision pipeline."""

    return has_conflicting_sensitive_facts(
        query,
        hits,
        min_similarity=min_similarity,
        min_priority=min_priority,
    )
