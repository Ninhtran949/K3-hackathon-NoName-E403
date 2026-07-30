import pytest

from app.safety import contains_likely_secret


@pytest.mark.parametrize(
    "text",
    [
        "ANTHROPIC_API_KEY=sk-ant-examplecredential123456789",
        "token: abcdefghijklmnopqrstuvwxyz.abcdef.abcdefghijklmnopqrstuvwxyz",
        "password = this-is-not-for-discord",
        "Dùng key sk-examplecredential123456789012345 để test",
    ],
)
def test_likely_credentials_are_detected(text: str) -> None:
    assert contains_likely_secret(text)


@pytest.mark.parametrize(
    "text",
    [
        "Làm sao cấu hình biến môi trường mà không lộ API key?",
        "Bot báo token không hợp lệ thì xử lý thế nào?",
        "Deadline Project 1 là khi nào?",
    ],
)
def test_normal_security_questions_are_not_flagged(text: str) -> None:
    assert not contains_likely_secret(text)
