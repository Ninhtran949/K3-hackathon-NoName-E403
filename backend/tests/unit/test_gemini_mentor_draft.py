from types import SimpleNamespace

import pytest

from src.core_rag_engine.adapters.outbound.gemini import (
    GeminiMentorDraftAdapter,
)


class FakeModels:
    def __init__(self, response) -> None:
        self.response = response
        self.last_config = None
        self.last_model = ""

    def generate_content(self, *, model, contents, config):
        self.last_model = model
        self.last_config = config
        return self.response


class FakeClient:
    def __init__(self, response) -> None:
        self.models = FakeModels(response)


def _grounded_response():
    text = "Giảm batch size để giảm lượng bộ nhớ GPU cần dùng."
    metadata = SimpleNamespace(
        web_search_queries=["PyTorch CUDA out of memory batch size"],
        grounding_chunks=[
            SimpleNamespace(
                web=SimpleNamespace(
                    uri="https://pytorch.org/docs/stable/notes/cuda.html",
                    title="PyTorch CUDA semantics",
                )
            ),
            SimpleNamespace(
                web=SimpleNamespace(
                    uri="https://pytorch.org/docs/stable/amp.html",
                    title="PyTorch AMP",
                )
            ),
        ],
        grounding_supports=[
            SimpleNamespace(
                segment=SimpleNamespace(
                    end_index=len(text),
                ),
                grounding_chunk_indices=[0, 1],
            )
        ],
    )
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(grounding_metadata=metadata)],
    )


def test_grounded_adapter_extracts_sources_and_inline_citations() -> None:
    client = FakeClient(_grounded_response())
    adapter = GeminiMentorDraftAdapter(
        api_key="unused",
        model="gemini-2.5-flash",
        system_prompt="Research with Google Search.",
        client=client,
    )

    draft = adapter.draft("Fix CUDA OOM?", context=[])

    assert draft.text.endswith("[1][2]")
    assert [source.title for source in draft.sources] == [
        "PyTorch CUDA semantics",
        "PyTorch AMP",
    ]
    assert draft.sources[0].source_url.startswith("https://pytorch.org/")
    assert "Truy vấn đã dùng" in draft.caveats[1]
    assert client.models.last_model == "gemini-2.5-flash"
    assert client.models.last_config.tools[0].google_search is not None


def test_grounded_adapter_deduplicates_urls() -> None:
    response = _grounded_response()
    duplicate = response.candidates[0].grounding_metadata.grounding_chunks[0]
    response.candidates[0].grounding_metadata.grounding_chunks.append(duplicate)
    client = FakeClient(response)
    adapter = GeminiMentorDraftAdapter(
        api_key="unused",
        model="gemini-2.5-flash",
        system_prompt="prompt",
        client=client,
    )

    draft = adapter.draft("Fix CUDA OOM?", context=[])

    assert len(draft.sources) == 2


def test_grounded_adapter_refuses_response_without_web_sources() -> None:
    response = SimpleNamespace(
        text="Một bản nháp không có nguồn.",
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[],
                    grounding_supports=[],
                    web_search_queries=[],
                )
            )
        ],
    )
    adapter = GeminiMentorDraftAdapter(
        api_key="unused",
        model="gemini-2.5-flash",
        system_prompt="prompt",
        client=FakeClient(response),
    )

    with pytest.raises(ValueError, match="groundingChunks"):
        adapter.draft("Câu hỏi?", context=[])
