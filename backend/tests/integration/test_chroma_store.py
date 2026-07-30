from pathlib import Path

from src.core_rag_engine.adapters.outbound.chromadb import ChromaVectorStoreAdapter
from src.core_rag_engine.domain import IngestDocument


def test_chroma_round_trip(tmp_path: Path) -> None:
    store = ChromaVectorStoreAdapter(tmp_path / "chroma", "test_collection")
    documents = [
        IngestDocument("doc-a", "Deadline 23:59", "Thông báo A"),
        IngestDocument("doc-b", "Hướng dẫn Docker", "Thông báo B"),
    ]
    store.upsert(documents, [[1.0, 0.0], [0.0, 1.0]])

    results = store.query([1.0, 0.0], top_k=2)

    assert results[0].document_id == "doc-a"
    assert results[0].score > 0.99
