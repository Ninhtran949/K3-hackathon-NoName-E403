from __future__ import annotations

import re

_LIKELY_SECRET_PATTERNS = (
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"""(?ix)
        \b(?:api[\s_-]*key|token|password|secret)\b
        \s*[:=]\s*
        ["']?[^\s"',;]{8,}
        """
    ),
)


def contains_likely_secret(text: str) -> bool:
    """Conservatively detect credentials that must never be indexed or forwarded."""

    return any(pattern.search(text) for pattern in _LIKELY_SECRET_PATTERNS)
