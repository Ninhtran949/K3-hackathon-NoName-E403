"""Public inbound contract used by delivery adapters."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import IngestDocument, MessageInput, ProcessingResult


class RAGEnginePort(Protocol):
    def handle_message(self, message: MessageInput) -> ProcessingResult:
        """Process one platform-independent message."""

    def ingest_documents(self, documents: Sequence[IngestDocument]) -> int:
        """Embed and persist static or imported documents."""
