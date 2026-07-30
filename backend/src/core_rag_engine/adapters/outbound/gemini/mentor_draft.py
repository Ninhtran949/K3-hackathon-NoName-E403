"""Gemini Google Search adapter for mentor-only, grounded drafts."""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

from google import genai
from google.genai import types

from ....domain import AnswerSource, MentorDraft, RetrievedChunk


class GeminiMentorDraftAdapter:
    """Research the public web and return a draft with verifiable citations."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        *,
        client: Any | None = None,
        maximum_sources: int = 5,
        maximum_draft_characters: int = 1400,
    ) -> None:
        if maximum_sources <= 0:
            raise ValueError("maximum_sources must be positive")
        if maximum_draft_characters <= 0:
            raise ValueError("maximum_draft_characters must be positive")
        self._client = client or genai.Client(api_key=api_key)
        self._model = model
        self._maximum_sources = maximum_sources
        self._maximum_draft_characters = maximum_draft_characters
        self._config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch(),
                )
            ],
        )

    def draft(
        self,
        question: str,
        context: Sequence[RetrievedChunk],
    ) -> MentorDraft:
        context_text = "\n\n".join(
            (
                f"TITLE: {chunk.title}\n"
                f"SIMILARITY: {chunk.score:.3f}\n"
                f"CONTENT:\n{chunk.text}"
            )
            for chunk in context
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=(
                f"CÂU HỎI CẦN RESEARCH:\n{question}\n\n"
                "CONTEXT NỘI BỘ CÓ THỂ YẾU; chỉ dùng để hiểu chủ đề, "
                "không coi là nguồn web đã xác minh:\n"
                f"{context_text or '[Không có context nội bộ phù hợp]'}"
            ),
            config=self._config,
        )
        draft_text = (response.text or "").strip()
        if not draft_text:
            raise ValueError("Gemini Search returned an empty mentor draft")

        metadata = self._grounding_metadata(response)
        sources, chunk_citations = self._extract_sources(metadata)
        if not sources:
            raise ValueError(
                "Gemini did not return groundingChunks; refusing ungrounded draft"
            )

        cited_text = self._add_inline_citations(
            draft_text,
            metadata,
            chunk_citations,
        )
        queries = tuple(
            str(query).strip()
            for query in (getattr(metadata, "web_search_queries", None) or ())
            if str(query).strip()
        )
        caveats = [
            "Nguồn web do Gemini Google Search tìm; mentor cần mở link kiểm tra "
            "trước khi duyệt.",
        ]
        if queries:
            caveats.append("Truy vấn đã dùng: " + "; ".join(queries[:2]))
        return MentorDraft(
            text=self._limit_text(cited_text),
            sources=sources,
            caveats=tuple(caveats),
        )

    @staticmethod
    def _grounding_metadata(response: Any) -> Any:
        candidates = getattr(response, "candidates", None) or ()
        if not candidates:
            raise ValueError("Gemini Search response has no candidates")
        metadata = getattr(candidates[0], "grounding_metadata", None)
        if metadata is None:
            raise ValueError("Gemini Search response has no grounding metadata")
        return metadata

    def _extract_sources(
        self,
        metadata: Any,
    ) -> tuple[tuple[AnswerSource, ...], dict[int, int]]:
        sources: list[AnswerSource] = []
        chunk_citations: dict[int, int] = {}
        citation_by_url: dict[str, int] = {}
        chunks = getattr(metadata, "grounding_chunks", None) or ()

        for chunk_index, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            url = str(getattr(web, "uri", "") or "").strip()
            if not url:
                continue
            existing = citation_by_url.get(url)
            if existing:
                chunk_citations[chunk_index] = existing
                continue
            if len(sources) >= self._maximum_sources:
                continue

            citation_number = len(sources) + 1
            title = str(getattr(web, "title", "") or "").strip() or url
            document_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
            sources.append(
                AnswerSource(
                    document_id=f"web:{document_hash}",
                    title=title,
                    source_url=url,
                )
            )
            citation_by_url[url] = citation_number
            chunk_citations[chunk_index] = citation_number
        return tuple(sources), chunk_citations

    @staticmethod
    def _add_inline_citations(
        text: str,
        metadata: Any,
        chunk_citations: dict[int, int],
    ) -> str:
        supports = getattr(metadata, "grounding_supports", None) or ()
        citations_by_end: dict[int, set[int]] = {}
        for support in supports:
            segment = getattr(support, "segment", None)
            end_index = getattr(segment, "end_index", None)
            if not isinstance(end_index, int) or not 0 <= end_index <= len(text):
                continue
            numbers = sorted(
                {
                    chunk_citations[index]
                    for index in (
                        getattr(support, "grounding_chunk_indices", None) or ()
                    )
                    if index in chunk_citations
                }
            )
            if numbers:
                citations_by_end.setdefault(end_index, set()).update(numbers)

        result = text
        for end_index, numbers in sorted(citations_by_end.items(), reverse=True):
            marker = "".join(f"[{number}]" for number in sorted(numbers))
            result = result[:end_index] + marker + result[end_index:]
        return result

    def _limit_text(self, text: str) -> str:
        if len(text) <= self._maximum_draft_characters:
            return text
        boundary = max(
            text.rfind("\n", 0, self._maximum_draft_characters),
            text.rfind(". ", 0, self._maximum_draft_characters),
        )
        if boundary < self._maximum_draft_characters // 2:
            boundary = self._maximum_draft_characters - 1
        return text[:boundary].rstrip() + "…"
