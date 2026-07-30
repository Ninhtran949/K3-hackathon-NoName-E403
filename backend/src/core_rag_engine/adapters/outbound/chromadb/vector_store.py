"""Persistent ChromaDB vector-store adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, cast

import chromadb

from ....domain import IngestDocument, MetadataValue, RetrievedChunk


class ChromaVectorStoreAdapter:
    def __init__(self, persist_directory: Path, collection_name: str) -> None:
        persist_directory.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_directory))
        self._collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        documents: Sequence[IngestDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        if len(documents) != len(embeddings):
            raise ValueError("Document and embedding counts must match")
        if not documents:
            return

        metadatas: list[dict[str, MetadataValue]] = []
        for document in documents:
            metadata = dict(document.metadata)
            metadata["title"] = document.title
            metadata["source_url"] = document.source_url
            metadatas.append(metadata)

        self._collection.upsert(
            ids=[document.document_id for document in documents],
            documents=[document.text for document in documents],
            embeddings=[list(vector) for vector in embeddings],
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []

        result = self._collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        chunks: list[RetrievedChunk] = []
        for document_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            safe_metadata = cast(dict[str, MetadataValue], dict(metadata or {}))
            title = str(safe_metadata.pop("title", document_id))
            source_url = str(safe_metadata.pop("source_url", ""))
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            chunks.append(
                RetrievedChunk(
                    document_id=str(document_id),
                    text=str(text),
                    title=title,
                    source_url=source_url,
                    score=score,
                    metadata=safe_metadata,
                )
            )
        return chunks
