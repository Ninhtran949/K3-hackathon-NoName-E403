"""Mentor routing contract."""

from __future__ import annotations

from typing import Protocol


class MentorRouterPort(Protocol):
    def route(self, text: str) -> str:
        """Return a Discord user/role mention for the supplied text."""
