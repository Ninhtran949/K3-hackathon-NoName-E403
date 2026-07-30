from pathlib import Path

from src.core_rag_engine.adapters.outbound.onboarding import (
    YamlOnboardingAdvisor,
)


def test_onboarding_advisor_selects_best_keyword_route(tmp_path: Path) -> None:
    config = tmp_path / "onboarding.yaml"
    config.write_text(
        """
default:
  suggestions:
    - title: Default
      target: "{monitored_channels}"
routes:
  - topic: devops
    keywords: [docker, deploy]
    suggestions:
      - title: DevOps guide
        target: https://example.com/devops
      - title: Support
        target: "{support_channel}"
""",
        encoding="utf-8",
    )
    advisor = YamlOnboardingAdvisor(
        config,
        placeholders={
            "monitored_channels": "<#1>",
            "support_channel": "<#2>",
        },
    )

    suggestions = advisor.suggest("Deploy Docker thế nào?", limit=2)

    assert [item.title for item in suggestions] == ["DevOps guide", "Support"]
    assert suggestions[1].target == "<#2>"


def test_onboarding_advisor_uses_default_and_honors_limit(
    tmp_path: Path,
) -> None:
    config = tmp_path / "onboarding.yaml"
    config.write_text(
        """
default:
  suggestions:
    - title: Start here
      target: "{monitored_channels}"
    - title: Support
      target: "{support_channel}"
routes: []
""",
        encoding="utf-8",
    )
    advisor = YamlOnboardingAdvisor(
        config,
        placeholders={
            "monitored_channels": "<#1>",
            "support_channel": "<#2>",
        },
    )

    suggestions = advisor.suggest("Câu hỏi chung?", limit=1)

    assert len(suggestions) == 1
    assert suggestions[0].target == "<#1>"
