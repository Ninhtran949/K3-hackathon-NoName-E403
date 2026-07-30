"""Composition root wiring ports to concrete adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core_rag_engine.adapters.outbound.activity import (
    SqliteLearnerActivityAdapter,
)
from ..core_rag_engine.adapters.outbound.chromadb import ChromaVectorStoreAdapter
from ..core_rag_engine.adapters.outbound.embeddings import (
    SentenceTransformerEmbeddingAdapter,
)
from ..core_rag_engine.adapters.outbound.gemini import (
    GeminiLLMAdapter,
    GeminiMentorDraftAdapter,
)
from ..core_rag_engine.adapters.outbound.onboarding import YamlOnboardingAdvisor
from ..core_rag_engine.adapters.outbound.routing import YamlMentorRouter
from ..core_rag_engine.adapters.outbound.support import SqliteSupportRepository
from ..core_rag_engine.application import CoreRAGEngine, SupportWorkflow
from .config_loader import load_engine_config, load_support_workflow_config
from .settings import Settings


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    engine: CoreRAGEngine
    support_workflow: SupportWorkflow
    project_root: Path


def build_container(project_root: Path | None = None) -> AppContainer:
    root = project_root or Path(__file__).resolve().parents[2]
    settings = Settings.load(root)
    settings.validate_runtime()

    engine_config = load_engine_config(
        settings.resolve_path(root, settings.app_config_path)
    )
    support_config = load_support_workflow_config(
        settings.resolve_path(root, settings.app_config_path)
    )
    system_prompt = settings.resolve_path(
        root, settings.system_prompt_path
    ).read_text(encoding="utf-8")

    embedding_provider = SentenceTransformerEmbeddingAdapter(
        settings.embedding_model
    )
    vector_store = ChromaVectorStoreAdapter(
        persist_directory=settings.resolve_path(root, settings.chroma_persist_dir),
        collection_name=settings.chroma_collection_name,
    )
    llm_provider = GeminiLLMAdapter(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        system_prompt=system_prompt,
    )
    mentor_draft_provider = GeminiMentorDraftAdapter(
        api_key=settings.gemini_api_key,
        model=settings.mentor_research_model,
        system_prompt=settings.resolve_path(
            root, settings.mentor_draft_prompt_path
        ).read_text(encoding="utf-8"),
    )
    mentor_router = YamlMentorRouter(
        settings.resolve_path(root, settings.routing_config_path)
    )
    learner_activity = SqliteLearnerActivityAdapter(
        settings.resolve_path(root, settings.onboarding_state_db_path)
    )
    monitored_channels = " ".join(
        f"<#{channel_id}>"
        for channel_id in sorted(settings.monitored_channel_ids())
    )
    onboarding_advisor = YamlOnboardingAdvisor(
        settings.resolve_path(root, settings.onboarding_config_path),
        placeholders={
            "monitored_channels": monitored_channels,
            "support_channel": f"<#{settings.support_channel_id()}>",
        },
    )
    support_repository = SqliteSupportRepository(
        settings.resolve_path(root, settings.support_state_db_path)
    )
    support_workflow = SupportWorkflow(
        repository=support_repository,
        config=support_config,
    )
    engine = CoreRAGEngine(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        llm_provider=llm_provider,
        mentor_router=mentor_router,
        learner_activity=learner_activity,
        onboarding_advisor=onboarding_advisor,
        mentor_draft_provider=mentor_draft_provider,
        support_repository=support_repository,
        config=engine_config,
    )
    return AppContainer(
        settings=settings,
        engine=engine,
        support_workflow=support_workflow,
        project_root=root,
    )
