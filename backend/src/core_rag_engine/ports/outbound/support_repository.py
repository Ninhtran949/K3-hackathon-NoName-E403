"""Persistence contract for escalation review and digest state."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import EscalationRecord


class SupportRepositoryPort(Protocol):
    def create(self, record: EscalationRecord) -> None:
        """Persist a new pending escalation."""

    def bind_context(self, review_id: str, support_context_id: str) -> bool:
        """Associate a delivery thread/channel with a pending review."""

    def find(
        self,
        *,
        review_id: str = "",
        support_context_id: str = "",
    ) -> EscalationRecord | None:
        """Find an escalation by explicit ID or support context."""

    def status(self, review_id: str) -> str:
        """Return the current workflow status."""

    def claim_for_delivery(self, review_id: str) -> bool:
        """Atomically transition pending to sending."""

    def mark_sent(self, review_id: str) -> None:
        """Mark a successfully delivered answer."""

    def restore_pending(self, review_id: str) -> None:
        """Return a failed delivery to pending."""

    def mark_rejected(self, review_id: str) -> bool:
        """Atomically reject a pending review."""

    def list_pending(self, limit: int) -> Sequence[EscalationRecord]:
        """List oldest outstanding escalations."""

    def last_digest_date(self) -> str:
        """Return the last successfully delivered local digest date."""

    def mark_digest_sent(self, report_date: str) -> None:
        """Persist a successfully delivered digest date."""
