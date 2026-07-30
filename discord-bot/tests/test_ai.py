from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.ai import (
    ANSWER_TOOL,
    AIProviderError,
    AnthropicAnswerGenerator,
    MalformedAIResponseError,
    SourceContext,
)


class FakeMessages:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, messages: FakeMessages) -> None:
        self.messages = messages


def tool_response(tool_input: object) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="submit_grounded_answer",
                input=tool_input,
            )
        ]
    )


def generator_for(messages: FakeMessages) -> AnthropicAnswerGenerator:
    return AnthropicAnswerGenerator(
        api_key="test-key",
        model="claude-test",
        timeout_seconds=12,
        max_retries=3,
        client=FakeClient(messages),
    )


def valid_input(*, message_id: str = "123456789") -> dict[str, object]:
    return {
        "answer": "Hạn nộp bài là 23:59 ngày 15/08.",
        "confidence": "high",
        "sources": [
            {
                "message_id": message_id,
                "label": "Thông báo deadline",
            }
        ],
        "topic": "deadline",
        "needs_human": False,
    }


def test_generate_parses_valid_forced_tool_response() -> None:
    messages = FakeMessages(tool_response(valid_input()))
    generator = generator_for(messages)
    source = SourceContext(
        message_id="123456789",
        content="BTC thông báo hạn nộp bài là 23:59 ngày 15/08.",
        author_role="admin",
        channel_name="announcements",
        timestamp="2026-08-01T09:00:00+07:00",
    )

    decision = asyncio.run(generator.generate("Hạn nộp bài là khi nào?", [source]))

    assert decision.answer == "Hạn nộp bài là 23:59 ngày 15/08."
    assert decision.confidence == "high"
    assert decision.source_ids == ("123456789",)
    assert decision.sources[0].label == "Thông báo deadline"
    assert decision.topic == "deadline"
    assert decision.needs_human is False

    call = messages.calls[0]
    assert call["tool_choice"] == {
        "type": "tool",
        "name": "submit_grounded_answer",
    }
    assert call["timeout"] == 12.0
    assert call["max_tokens"] == 2500
    # Claude Sonnet 5 only accepts its default temperature.
    assert "temperature" not in call
    assert call["tools"] == [ANSWER_TOOL]
    assert ANSWER_TOOL["strict"] is True
    assert ANSWER_TOOL["input_schema"]["additionalProperties"] is False
    assert "untrusted data" in str(call["system"])
    assert "123456789" in str(call["messages"])


def test_strict_tool_schema_uses_only_supported_constraints() -> None:
    serialized_schema = json.dumps(ANSWER_TOOL["input_schema"])

    for unsupported_keyword in (
        '"pattern"',
        '"minLength"',
        '"maxLength"',
        '"maxItems"',
    ):
        assert unsupported_keyword not in serialized_schema


def test_unknown_source_reference_is_left_for_pipeline_validation() -> None:
    messages = FakeMessages(tool_response(valid_input(message_id="invented-source")))
    generator = generator_for(messages)
    source = SourceContext(message_id="known-source", content="Nội dung nguồn thật.")

    decision = asyncio.run(generator.generate("Câu hỏi?", [source]))

    assert decision.source_ids == ("invented-source",)


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(content=[]),
        SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="another_tool",
                    input=valid_input(),
                )
            ]
        ),
        tool_response({"answer": "Thiếu các trường bắt buộc"}),
        tool_response({**valid_input(), "needs_human": "false"}),
        tool_response({**valid_input(), "confidence": "medium"}),
        tool_response(
            {
                **valid_input(),
                "sources": [{"message_id": 123, "label": "Nguồn"}],
            }
        ),
        tool_response(
            {
                **valid_input(),
                "answer": "Xem tại https://untrusted.example/answer",
            }
        ),
        tool_response({**valid_input(), "answer": "Xem discord.gg/invite-code"}),
        tool_response({**valid_input(), "answer": "Xem example.com/answer"}),
    ],
)
def test_malformed_response_raises_safe_typed_error(response: object) -> None:
    generator = generator_for(FakeMessages(response))

    with pytest.raises(
        MalformedAIResponseError,
        match="invalid response",
    ) as caught:
        asyncio.run(generator.generate("Một câu hỏi bí mật", []))

    assert "Một câu hỏi bí mật" not in str(caught.value)
    assert "test-key" not in str(caught.value)


def test_provider_failure_raises_safe_typed_error_without_leaking_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "super-secret-key"
    question = "Câu hỏi không được lộ"
    messages = FakeMessages(
        error=RuntimeError(f"provider echoed {secret} and {question}"),
    )
    generator = AnthropicAnswerGenerator(
        api_key=secret,
        model="claude-test",
        client=FakeClient(messages),
    )

    with pytest.raises(AIProviderError, match="temporarily unavailable") as caught:
        asyncio.run(generator.generate(question, []))

    rendered_error = str(caught.value)
    assert secret not in rendered_error
    assert question not in rendered_error
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert secret not in caplog.text
    assert question not in caplog.text


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_incomplete_or_refused_response_raises_safe_provider_error(
    stop_reason: str,
) -> None:
    response = SimpleNamespace(stop_reason=stop_reason, content=[])
    generator = generator_for(FakeMessages(response))

    with pytest.raises(AIProviderError):
        asyncio.run(generator.generate("Câu hỏi?", []))
