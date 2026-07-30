"""Deterministic keyword routing for mentor/support roles.

The router deliberately stays independent from Discord so its decisions can be
tested without a network connection.  Configuration is loaded from JSON and is
validated before any routing takes place.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

RoleId: TypeAlias = str | int


@dataclass(frozen=True, slots=True)
class Route:
    """A single routing rule, in its original configuration order."""

    name: str
    keywords: tuple[str, ...]
    role_id: RoleId | None = None
    priority: int = 0


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Result of routing one piece of text."""

    route_name: str | None
    role_id: RoleId | None
    score: int
    matched_keywords: tuple[str, ...]
    is_default: bool

    @property
    def name(self) -> str | None:
        """Short alias useful when displaying a decision."""

        return self.route_name


@dataclass(frozen=True, slots=True)
class RoutingConfig:
    """Validated routing configuration."""

    routes: tuple[Route, ...]
    default_role_id: RoleId | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RoutingConfig:
        """Build and validate configuration from an already-decoded JSON object."""

        if not isinstance(data, Mapping):
            raise ValueError("Routing config phải là một JSON object")
        return _parse_config(data)

    @classmethod
    def from_file(cls, path: str | Path) -> RoutingConfig:
        """Load and validate a UTF-8 JSON configuration file."""

        config_path = Path(path)
        try:
            raw = config_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise ValueError(f"Không thể đọc routing config '{config_path}': {error}") from error

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(
                "Routing config không phải JSON hợp lệ "
                f"(dòng {error.lineno}, cột {error.colno}): {error.msg}"
            ) from error

        if not isinstance(data, Mapping):
            raise ValueError("Routing config phải là một JSON object")
        return cls.from_dict(data)

    def decide(self, text: str) -> RouteDecision:
        """Choose a route for ``text``."""

        return decide_route(text, self)

    def route(self, text: str) -> RouteDecision:
        """Alias for :meth:`decide`."""

        return self.decide(text)


class KeywordRouter:
    """Small stateful facade for callers that keep one config in memory."""

    def __init__(self, config: RoutingConfig) -> None:
        if not isinstance(config, RoutingConfig):
            raise TypeError("config phải là một RoutingConfig")
        self.config = config

    @classmethod
    def from_file(cls, path: str | Path) -> KeywordRouter:
        return cls(RoutingConfig.from_file(path))

    def decide(self, text: str) -> RouteDecision:
        return self.config.decide(text)

    def route(self, text: str) -> RouteDecision:
        return self.decide(text)


def normalize_text(value: str) -> str:
    """Normalize case, accents, punctuation, symbols, and whitespace.

    Punctuation is converted to a word separator rather than removed, so
    ``"fine-tune"`` and ``"fine tune"`` normalize to the same phrase without
    accidentally joining unrelated words.  Vietnamese ``đ`` needs an explicit
    mapping because Unicode decomposition does not turn it into ``d``.
    """

    if not isinstance(value, str):
        raise ValueError("Nội dung cần chuẩn hóa phải là chuỗi")

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    normalized: list[str] = []

    for character in decomposed:
        if character == "đ":
            normalized.append("d")
            continue

        category = unicodedata.category(character)
        if category.startswith("M"):
            # Combining marks carry accents after NFKD decomposition.
            continue
        if category.startswith(("L", "N")):
            normalized.append(character)
        else:
            normalized.append(" ")

    return " ".join("".join(normalized).split())


def load_routing_config(path: str | Path) -> RoutingConfig:
    """Load a :class:`RoutingConfig` from ``path``."""

    return RoutingConfig.from_file(path)


def decide_route(text: str, config: RoutingConfig) -> RouteDecision:
    """Return the highest-scoring deterministic routing decision.

    Each distinct configured keyword or phrase contributes one point when it
    appears as a complete token/phrase.  Repeated occurrences do not inflate
    the score.  Ties are resolved by higher ``priority``, then by the route's
    original order in the JSON file.
    """

    if not isinstance(config, RoutingConfig):
        raise TypeError("config phải là một RoutingConfig")

    normalized_text = normalize_text(text)
    text_tokens = tuple(normalized_text.split())

    best_route: Route | None = None
    best_score = 0
    best_priority = 0
    best_matches: tuple[str, ...] = ()

    for route in config.routes:
        matches = tuple(
            keyword
            for keyword in route.keywords
            if _contains_phrase(text_tokens, tuple(normalize_text(keyword).split()))
        )
        score = len(matches)
        if score == 0:
            continue

        if (
            best_route is None
            or score > best_score
            or (score == best_score and route.priority > best_priority)
        ):
            best_route = route
            best_score = score
            best_priority = route.priority
            best_matches = matches

    if best_route is None:
        return RouteDecision(
            route_name=None,
            role_id=config.default_role_id,
            score=0,
            matched_keywords=(),
            is_default=True,
        )

    return RouteDecision(
        route_name=best_route.name,
        role_id=best_route.role_id,
        score=best_score,
        matched_keywords=best_matches,
        is_default=False,
    )


def route_text(text: str, config: RoutingConfig) -> RouteDecision:
    """Compatibility alias for :func:`decide_route`."""

    return decide_route(text, config)


def _contains_phrase(text_tokens: tuple[str, ...], phrase_tokens: tuple[str, ...]) -> bool:
    if not text_tokens or not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False

    phrase_length = len(phrase_tokens)
    return any(
        text_tokens[index : index + phrase_length] == phrase_tokens
        for index in range(len(text_tokens) - phrase_length + 1)
    )


def _parse_config(data: Mapping[str, Any]) -> RoutingConfig:
    allowed_root_fields = {"routes", "default_role_id"}
    unknown_root_fields = [field for field in data if field not in allowed_root_fields]
    if unknown_root_fields:
        fields = ", ".join(repr(field) for field in unknown_root_fields)
        raise ValueError(f"Routing config có field không hỗ trợ: {fields}")

    if "routes" not in data:
        raise ValueError("Routing config thiếu field 'routes'")
    raw_routes = data["routes"]
    if not isinstance(raw_routes, list):
        raise ValueError("Routing config field 'routes' phải là một danh sách")

    routes: list[Route] = []
    seen_names: set[str] = set()
    for index, raw_route in enumerate(raw_routes):
        route = _parse_route(raw_route, index)
        comparable_name = route.name.casefold()
        if comparable_name in seen_names:
            raise ValueError(f"routes[{index}].name bị trùng: '{route.name}'")
        seen_names.add(comparable_name)
        routes.append(route)

    default_role_id = _parse_role_id(
        data.get("default_role_id"),
        "default_role_id",
    )
    return RoutingConfig(routes=tuple(routes), default_role_id=default_role_id)


def _parse_route(raw_route: Any, index: int) -> Route:
    location = f"routes[{index}]"
    if not isinstance(raw_route, Mapping):
        raise ValueError(f"{location} phải là một JSON object")

    allowed_fields = {"name", "keywords", "role_id", "priority"}
    unknown_fields = [field for field in raw_route if field not in allowed_fields]
    if unknown_fields:
        fields = ", ".join(repr(field) for field in unknown_fields)
        raise ValueError(f"{location} có field không hỗ trợ: {fields}")

    raw_name = raw_route.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError(f"{location}.name phải là chuỗi không rỗng")
    name = raw_name.strip()

    raw_keywords = raw_route.get("keywords")
    if not isinstance(raw_keywords, list) or not raw_keywords:
        raise ValueError(f"{location}.keywords phải là danh sách không rỗng")

    keywords: list[str] = []
    normalized_keywords: set[str] = set()
    for keyword_index, raw_keyword in enumerate(raw_keywords):
        keyword_location = f"{location}.keywords[{keyword_index}]"
        if not isinstance(raw_keyword, str) or not raw_keyword.strip():
            raise ValueError(f"{keyword_location} phải là chuỗi không rỗng")

        keyword = raw_keyword.strip()
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            raise ValueError(f"{keyword_location} phải chứa ít nhất một chữ cái hoặc chữ số")
        if normalized_keyword in normalized_keywords:
            raise ValueError(f"{keyword_location} bị trùng sau khi chuẩn hóa: '{keyword}'")
        normalized_keywords.add(normalized_keyword)
        keywords.append(keyword)

    priority = raw_route.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError(f"{location}.priority phải là số nguyên")

    role_id = _parse_role_id(raw_route.get("role_id"), f"{location}.role_id")
    return Route(
        name=name,
        keywords=tuple(keywords),
        role_id=role_id,
        priority=priority,
    )


def _parse_role_id(value: Any, location: str) -> RoleId | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{location} phải là chuỗi không rỗng hoặc số nguyên dương")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{location} phải là số nguyên dương")
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{location} phải là chuỗi không rỗng hoặc số nguyên dương")
