"""Public inbound contract for mentor support workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ...domain import DigestResult, MentorDecisionInput, ReviewDecisionResult


class SupportWorkflowPort(Protocol):
    @property
    def digest_poll_seconds(self) -> int:
        """Seconds between scheduled digest checks."""

    def bind_review_context(
        self,
        review_id: str,
        support_context_id: str,
    ) -> bool:
        """Bind a Discord support thread to a review."""

    def decide(self, decision: MentorDecisionInput) -> ReviewDecisionResult:
        """Validate and prepare a mentor decision."""

    def complete_delivery(self, review_id: str, succeeded: bool) -> None:
        """Commit or roll back delivery state."""

    def build_digest(
        self,
        now: datetime,
        *,
        force: bool = False,
    ) -> DigestResult | None:
        """Build a due or manually requested digest."""

    def mark_digest_sent(self, report_date: str) -> None:
        """Persist successful digest delivery."""
