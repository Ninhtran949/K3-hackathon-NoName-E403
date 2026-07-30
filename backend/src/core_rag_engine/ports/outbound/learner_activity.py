"""Persistence contract for learner activity."""

from __future__ import annotations

from typing import Protocol

from ...domain import MessageInput


class LearnerActivityPort(Protocol):
    def claim_first_question(self, message: MessageInput) -> bool:
        """Atomically mark and report a learner's first question in a channel."""
