"""Contract for selecting onboarding resources."""

from __future__ import annotations

from typing import Protocol, Sequence

from ...domain import OnboardingSuggestion


class OnboardingAdvisorPort(Protocol):
    def suggest(
        self,
        question: str,
        limit: int,
    ) -> Sequence[OnboardingSuggestion]:
        """Return relevant starting resources for a learner."""
