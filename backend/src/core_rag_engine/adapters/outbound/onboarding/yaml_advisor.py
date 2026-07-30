"""Keyword-based onboarding suggestions loaded from YAML."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from ....domain import OnboardingSuggestion


class YamlOnboardingAdvisor:
    """Select a configured topic route and return its starting resources."""

    def __init__(
        self,
        config_path: Path,
        placeholders: Mapping[str, str] | None = None,
    ) -> None:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        self._default = self._parse_suggestions(raw.get("default", {}))
        self._routes = tuple(self._parse_route(route) for route in raw.get("routes", []))
        self._placeholders = _PlaceholderMap(placeholders or {})

    def suggest(
        self,
        question: str,
        limit: int,
    ) -> Sequence[OnboardingSuggestion]:
        if limit <= 0:
            return ()

        normalized = question.casefold()
        best_score = 0
        selected = self._default
        for keywords, suggestions in self._routes:
            score = sum(keyword in normalized for keyword in keywords)
            if score > best_score:
                best_score = score
                selected = suggestions

        rendered: list[OnboardingSuggestion] = []
        seen: set[tuple[str, str]] = set()
        for suggestion in selected:
            item = OnboardingSuggestion(
                title=suggestion.title.format_map(self._placeholders),
                target=suggestion.target.format_map(self._placeholders),
            )
            key = (item.title, item.target)
            if key in seen:
                continue
            seen.add(key)
            rendered.append(item)
            if len(rendered) == limit:
                break
        return tuple(rendered)

    @classmethod
    def _parse_route(
        cls,
        raw: Mapping[str, object],
    ) -> tuple[tuple[str, ...], tuple[OnboardingSuggestion, ...]]:
        keywords = tuple(
            str(keyword).strip().casefold()
            for keyword in raw.get("keywords", [])
            if str(keyword).strip()
        )
        return keywords, cls._parse_suggestions(raw)

    @staticmethod
    def _parse_suggestions(
        raw: Mapping[str, object],
    ) -> tuple[OnboardingSuggestion, ...]:
        parsed: list[OnboardingSuggestion] = []
        for item in raw.get("suggestions", []):
            if not isinstance(item, Mapping):
                continue
            title = str(item.get("title", "")).strip()
            target = str(item.get("target", "")).strip()
            if title and target:
                parsed.append(OnboardingSuggestion(title=title, target=target))
        return tuple(parsed)


class _PlaceholderMap(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
