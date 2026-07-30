"""Vector persistence contract."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import IngestDocument, RetrievedChunk


class VectorStorePort(Protocol):
    def upsert(
        self,
        documents: Sequence[IngestDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        """Persist documents and their embeddings."""

    def query(
        self,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Return the nearest chunks ordered by relevance."""
