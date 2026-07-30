"""Embedding provider contract."""

from __future__ import annotations

from typing import Protocol, Sequence


class EmbeddingProviderPort(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed documents in the configured vector space."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a query in the same vector space."""
