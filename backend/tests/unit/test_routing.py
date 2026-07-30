from pathlib import Path

from src.core_rag_engine.adapters.outbound.routing import YamlMentorRouter


def test_keyword_route_and_placeholder_fallback(tmp_path: Path) -> None:
    config = tmp_path / "routing.yaml"
    config.write_text(
        """
default:
  mentor_mention: "<@999>"
routes:
  - topic: devops
    keywords: [docker, deploy]
    mentor_mention: "<@123>"
  - topic: ml
    keywords: [model]
    mentor_mention: "<@&ML_ROLE_ID>"
""".strip(),
        encoding="utf-8",
    )
    router = YamlMentorRouter(config)

    assert router.route("Docker bị lỗi") == "<@123>"
    assert router.route("Model bị lỗi") == "<@999>"
    assert router.route("Câu hỏi khác") == "<@999>"
