from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.routing import RoutingConfig, decide_route, load_routing_config, normalize_text


def make_config(*routes: dict[str, object], default: str | None = "on-call") -> RoutingConfig:
    return RoutingConfig.from_dict(
        {
            "routes": list(routes),
            "default_role_id": default,
        }
    )


def test_normalize_text_handles_unicode_accents_case_punctuation_and_spaces() -> None:
    assert normalize_text("  ĐIỂM—Chấm,   BÀI?!  ") == "diem cham bai"
    assert normalize_text("Straße / STRASSE") == "strasse strasse"


def test_route_matches_complete_normalized_keyword_and_phrase() -> None:
    config = make_config(
        {
            "name": "academic",
            "keywords": ["điểm", "chấm bài"],
            "role_id": "academic-role",
        },
        {
            "name": "ml",
            "keywords": ["ai"],
            "role_id": "ml-role",
        },
    )

    decision = decide_route("Cho mình hỏi cách CHẤM-BÀI và tính diem?", config)

    assert decision.route_name == "academic"
    assert decision.role_id == "academic-role"
    assert decision.score == 2
    assert decision.matched_keywords == ("điểm", "chấm bài")
    assert decision.is_default is False

    # A token keyword must not match inside a larger token such as "training".
    assert decide_route("training model", config).is_default is True


def test_route_chooses_most_distinct_keywords_without_counting_repetitions() -> None:
    config = make_config(
        {
            "name": "devops",
            "keywords": ["deploy", "docker"],
            "role_id": "devops-role",
        },
        {
            "name": "general",
            "keywords": ["deploy"],
            "role_id": "general-role",
            "priority": 100,
        },
    )

    decision = config.decide("Docker deploy deploy deploy")

    assert decision.route_name == "devops"
    assert decision.score == 2


def test_equal_score_uses_priority_then_original_order() -> None:
    priority_config = make_config(
        {
            "name": "first",
            "keywords": ["server"],
            "role_id": "first-role",
            "priority": 1,
        },
        {
            "name": "second",
            "keywords": ["server"],
            "role_id": "second-role",
            "priority": 2,
        },
    )
    assert priority_config.route("server").route_name == "second"

    order_config = make_config(
        {
            "name": "first",
            "keywords": ["server"],
            "role_id": "first-role",
            "priority": 2,
        },
        {
            "name": "second",
            "keywords": ["server"],
            "role_id": "second-role",
            "priority": 2,
        },
    )
    assert order_config.route("server").route_name == "first"


def test_no_match_returns_default_role() -> None:
    config = make_config(
        {
            "name": "devops",
            "keywords": ["docker"],
            "role_id": "devops-role",
        }
    )

    decision = config.decide("Câu hỏi không thuộc chủ đề nào")

    assert decision.route_name is None
    assert decision.role_id == "on-call"
    assert decision.score == 0
    assert decision.matched_keywords == ()
    assert decision.is_default is True


def test_load_routing_config_from_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / "routing.json"
    path.write_text(
        json.dumps(
            {
                "routes": [
                    {
                        "name": "academic",
                        "keywords": ["điểm"],
                        "role_id": 123456,
                    }
                ],
                "default_role_id": 987654,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = load_routing_config(path)

    assert config.routes[0].keywords == ("điểm",)
    assert config.routes[0].role_id == 123456
    assert config.default_role_id == 987654


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "JSON object"),
        ({}, "routes"),
        ({"routes": "bad"}, "danh sách"),
        ({"routes": [None]}, r"routes\[0\]"),
        ({"routes": [{"name": "", "keywords": ["x"]}]}, "name"),
        ({"routes": [{"name": "x", "keywords": []}]}, "keywords"),
        (
            {"routes": [{"name": "x", "keywords": ["AI", "ai"]}]},
            "trùng sau khi chuẩn hóa",
        ),
        (
            {"routes": [{"name": "x", "keywords": ["ok"], "priority": True}]},
            "priority",
        ),
        (
            {"routes": [{"name": "x", "keywords": ["ok"], "unexpected": 1}]},
            "không hỗ trợ",
        ),
    ],
)
def test_malformed_config_raises_clear_value_error(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    path = tmp_path / "routing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_routing_config(path)


def test_from_dict_rejects_a_non_mapping_root() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        RoutingConfig.from_dict([])  # type: ignore[arg-type]


def test_invalid_json_raises_value_error_with_location(tmp_path: Path) -> None:
    path = tmp_path / "routing.json"
    path.write_text('{"routes": [}', encoding="utf-8")

    with pytest.raises(ValueError, match=r"dòng \d+, cột \d+"):
        load_routing_config(path)
