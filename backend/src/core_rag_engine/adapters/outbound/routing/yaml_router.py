"""YAML-backed deterministic keyword router."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class Route:
    keywords: tuple[str, ...]
    mentor_mention: str


class YamlMentorRouter:
    def __init__(self, config_path: Path) -> None:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        self._default_mention = str(
            (raw.get("default") or {}).get("mentor_mention", "")
        ).strip()
        if not self._is_usable_mention(self._default_mention):
            raise ValueError("routing.yaml must contain a real default mentor mention")

        self._routes = tuple(
            Route(
                keywords=tuple(
                    str(keyword).casefold()
                    for keyword in route.get("keywords", [])
                    if str(keyword).strip()
                ),
                mentor_mention=str(route.get("mentor_mention", "")).strip(),
            )
            for route in raw.get("routes", [])
        )

    def route(self, text: str) -> str:
        normalized = text.casefold()
        for route in self._routes:
            if (
                self._is_usable_mention(route.mentor_mention)
                and any(keyword in normalized for keyword in route.keywords)
            ):
                return route.mentor_mention
        return self._default_mention

    @staticmethod
    def _is_usable_mention(value: str) -> bool:
        if not (value.startswith("<@") and value.endswith(">")):
            return False
        upper = value.upper()
        return "_ID" not in upper and "ROLE_ID" not in upper and "USER_ID" not in upper
