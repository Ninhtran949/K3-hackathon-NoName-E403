"""Google Gemini adapter with structured, validated output."""

from __future__ import annotations

from typing import Literal, Sequence

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from ....domain import Confidence, LLMAnswer, RetrievedChunk


class GeminiAnswerPayload(BaseModel):
    answer: str = Field(min_length=1)
    confidence: Literal["high", "low"]
    source_ids: list[str] = Field(default_factory=list)


class GeminiLLMAdapter:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=GeminiAnswerPayload,
        )

    def answer(
        self,
        question: str,
        context: Sequence[RetrievedChunk],
    ) -> LLMAnswer:
        context_text = "\n\n".join(
            (
                f"[SOURCE_ID={chunk.document_id}]\n"
                f"TITLE: {chunk.title}\n"
                f"CONTENT:\n{chunk.text}"
            )
            for chunk in context
        )
        prompt = (
            "CÂU HỎI:\n"
            f"{question}\n\n"
            "NGỮ CẢNH ĐƯỢC RETRIEVE:\n"
            f"{context_text}"
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config,
        )

        parsed = response.parsed
        if isinstance(parsed, GeminiAnswerPayload):
            payload = parsed
        elif isinstance(parsed, dict):
            payload = GeminiAnswerPayload.model_validate(parsed)
        else:
            payload = GeminiAnswerPayload.model_validate_json(response.text or "")

        return LLMAnswer(
            answer=payload.answer,
            confidence=Confidence(payload.confidence),
            source_ids=tuple(payload.source_ids),
        )
