"""Load external application configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..core_rag_engine.application import (
    EngineConfig,
    SupportWorkflowConfig,
)


def load_engine_config(path: Path) -> EngineConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    question = raw.get("question_detection") or {}
    retrieval = raw.get("retrieval") or {}
    onboarding = raw.get("onboarding") or {}
    mentor_research = raw.get("mentor_research") or {}
    return EngineConfig(
        question_mode=str(question.get("mode", "question_mark")),
        ignore_bot_messages=bool(question.get("ignore_bot_messages", True)),
        minimum_text_length=int(question.get("minimum_text_length", 3)),
        top_k=int(retrieval.get("top_k", 5)),
        minimum_similarity=float(retrieval.get("minimum_similarity", 0.45)),
        maximum_sources=int(retrieval.get("maximum_sources", 3)),
        onboarding_enabled=bool(onboarding.get("enabled", True)),
        onboarding_suggestion_limit=int(
            onboarding.get("maximum_suggestions", 2)
        ),
        mentor_research_enabled=bool(mentor_research.get("enabled", True)),
    )


def load_support_workflow_config(path: Path) -> SupportWorkflowConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    digest = raw.get("digest") or {}
    mentor_research = raw.get("mentor_research") or {}
    return SupportWorkflowConfig(
        digest_enabled=bool(digest.get("enabled", True)),
        digest_timezone=str(digest.get("timezone", "Asia/Bangkok")),
        digest_hour=int(digest.get("hour", 23)),
        digest_minute=int(digest.get("minute", 0)),
        digest_maximum_items=int(digest.get("maximum_items", 10)),
        digest_poll_seconds=int(digest.get("poll_seconds", 60)),
        maximum_approved_answer_length=int(
            mentor_research.get("maximum_approved_answer_length", 1600)
        ),
    )
