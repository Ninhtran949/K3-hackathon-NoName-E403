"""Local sentence-transformers embedding adapter."""

from __future__ import annotations

from threading import Lock
from typing import Sequence

from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddingAdapter:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = Lock()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    self._model = SentenceTransformer(self._model_name)
        return self._model
