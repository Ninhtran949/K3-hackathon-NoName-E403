from __future__ import annotations

import pytest

from app.models import KnowledgeSource
from app.retrieval import (
    RetrievalService,
    detect_conflicts,
    find_temporal_conflicts,
    is_sensitive_fact,
    lexical_similarity,
    tokenize,
)


def source(
    key: str,
    content: str,
    *,
    priority: int = 0,
    official: bool = False,
    pinned: bool = False,
) -> KnowledgeSource:
    return KnowledgeSource(
        source_key=key,
        content=content,
        source_url=f"https://discord.test/{key}",
        priority=priority,
        official=official,
        is_pinned=pinned,
    )


def test_vietnamese_matching_is_case_and_accent_insensitive() -> None:
    accented = tokenize("HẠN CHÓT nộp Bài Project Một")
    unaccented = tokenize("han chot nop bai project mot")

    assert accented == unaccented
    assert "deadline" in accented
    assert (
        lexical_similarity(
            "Hạn chót nộp Project 1 là khi nào?",
            "Deadline nộp project 1 là 23:59 ngày 15/08.",
        )
        >= 0.8
    )


def test_irrelevant_source_is_not_rescued_by_official_priority() -> None:
    service = RetrievalService(top_k=5, threshold=0.3, authority_bonus=0.2)
    sources = [
        source(
            "official-but-irrelevant",
            "Thông báo lịch nghỉ và hoạt động thể thao cuối tuần.",
            priority=10,
            official=True,
        ),
        source("relevant", "Rubric Project 1 có bốn tiêu chí chấm bài."),
    ]

    hits = service.search("Rubric chấm Project 1", sources)

    assert [hit.source.source_key for hit in hits] == ["relevant"]


def test_authority_is_a_deterministic_ranking_bonus() -> None:
    service = RetrievalService(top_k=5, threshold=0.2)
    sources = [
        source("community", "Deadline Project 1 là ngày 15/08."),
        source(
            "official",
            "Deadline Project 1 là ngày 15/08.",
            priority=8,
            official=True,
        ),
    ]

    first_run = service.search("Deadline Project 1", sources)
    second_run = service.search("Deadline Project 1", reversed(sources))

    assert [hit.source.source_key for hit in first_run] == ["official", "community"]
    assert [hit.source.source_key for hit in second_run] == ["official", "community"]
    assert first_run[0].similarity == first_run[1].similarity
    assert first_run[0].ranking_score > first_run[1].ranking_score


def test_service_applies_threshold_and_top_k() -> None:
    sources = [
        source("one", "Deadline Project 1 là 15/08."),
        source("two", "Project 1 cần nộp mã nguồn."),
        source("three", "Thông báo workshop thiết kế sản phẩm."),
    ]
    service = RetrievalService(top_k=1, threshold=0.5)

    hits = service.search("Deadline Project 1", sources)

    assert len(hits) == 1
    assert hits[0].source.source_key == "one"
    assert service.search("Deadline Project 1", sources, threshold=0.95) == []

    with pytest.raises(ValueError, match="top_k"):
        service.search("deadline", sources, top_k=0)
    with pytest.raises(ValueError, match="threshold"):
        service.search("deadline", sources, threshold=1.1)


def test_sensitive_fact_helper_covers_required_topics() -> None:
    assert is_sensitive_fact("Deadline là ngày nào?")
    assert is_sensitive_fact("Rubric chấm điểm ra sao?")
    assert is_sensitive_fact("Quy định nộp bài có thay đổi không?")
    assert is_sensitive_fact("Lịch học tuần này có thay đổi không?")
    assert is_sensitive_fact("Workshop có bị hủy sự kiện không?")
    assert not is_sensitive_fact("Hôm nay mọi người ăn gì?")


def test_detects_distinct_dates_across_relevant_high_trust_sources() -> None:
    query = "Deadline Project 1 là khi nào?"
    sources = [
        source(
            "old",
            "Deadline Project 1 là 23:59 ngày 15/08/2026.",
            official=True,
        ),
        source(
            "new",
            "Deadline Project 1 là 23:59 ngày 16/08/2026.",
            priority=5,
            pinned=True,
        ),
    ]
    hits = RetrievalService(threshold=0.2).search(query, sources)

    conflicts = find_temporal_conflicts(query, hits)

    assert detect_conflicts(query, hits)
    assert len(conflicts) == 1
    assert conflicts[0].fact_kind == "date"
    assert {conflicts[0].left_value, conflicts[0].right_value} == {
        "15/08/2026",
        "16/08/2026",
    }


def test_conflict_detection_avoids_ambiguous_and_low_trust_false_positives() -> None:
    service = RetrievalService(threshold=0.2)
    query = "Deadline Project 1 là khi nào?"

    ambiguous_hits = service.search(
        query,
        [
            source(
                "change",
                "Deadline Project 1 đổi từ ngày 15/08 sang ngày 16/08.",
                official=True,
            ),
            source(
                "current",
                "Deadline Project 1 là ngày 16/08.",
                official=True,
            ),
        ],
    )
    assert not detect_conflicts(query, ambiguous_hits)

    low_trust_hits = service.search(
        query,
        [
            source("rumour-a", "Deadline Project 1 là ngày 15/08."),
            source("rumour-b", "Deadline Project 1 là ngày 16/08."),
        ],
    )
    assert not detect_conflicts(query, low_trust_hits)

    # A broad question has no subject anchor, so dates from unrelated projects
    # must not be presented as a contradiction.
    broad_hits = service.search(
        "Deadline là khi nào?",
        [
            source("p1", "Deadline Project 1 là ngày 15/08.", official=True),
            source("p2", "Deadline Project 2 là ngày 20/08.", official=True),
        ],
    )
    assert not detect_conflicts("Deadline là khi nào?", broad_hits)

    score_hits = service.search(
        "Điểm Project 1 là bao nhiêu?",
        [
            source("score-a", "Điểm Project 1 là 8/10.", official=True),
            source("score-b", "Điểm Project 1 là 7/10.", official=True),
        ],
    )
    assert not detect_conflicts("Điểm Project 1 là bao nhiêu?", score_hits)
