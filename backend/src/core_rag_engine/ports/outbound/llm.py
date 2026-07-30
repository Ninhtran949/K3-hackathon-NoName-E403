"""LLM provider contract."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import LLMAnswer, RetrievedChunk


class LLMProviderPort(Protocol):
    def answer(
        self,
        question: str,
        context: Sequence[RetrievedChunk],
    ) -> LLMAnswer:
        """Return a grounded answer and model confidence."""
