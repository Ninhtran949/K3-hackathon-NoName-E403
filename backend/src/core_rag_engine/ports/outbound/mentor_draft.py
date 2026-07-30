"""Contract for generating mentor-only answer drafts."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import MentorDraft, RetrievedChunk


class MentorDraftProviderPort(Protocol):
    def draft(
        self,
        question: str,
        context: Sequence[RetrievedChunk],
    ) -> MentorDraft:
        """Create a draft that must be reviewed before student delivery."""
