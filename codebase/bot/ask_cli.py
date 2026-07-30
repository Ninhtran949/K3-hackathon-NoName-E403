from __future__ import annotations

import argparse
from pathlib import Path

from bot.config import load_settings
from bot.gemini_client import GeminiEngine
from bot.pipeline import AnswerPipeline
from bot.rag import KnowledgeBase


def ensure_knowledge(kb: KnowledgeBase, knowledge_dir: Path, reset: bool = False) -> None:
    if reset or kb.count() == 0:
        if reset:
            kb.reset()
        n = kb.ingest_markdown_dir(knowledge_dir)
        print(f"Indexed {n} chunks from {knowledge_dir}")
    else:
        print(f"KB already has {kb.count()} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI test RAG assistant (no Discord)")
    parser.add_argument("question", nargs="?", help="Câu hỏi")
    parser.add_argument("--reindex", action="store_true", help="Xoá và index lại knowledge/")
    args = parser.parse_args()

    settings = load_settings()
    kb = KnowledgeBase(settings.kb_dir)
    ensure_knowledge(kb, settings.knowledge_dir, reset=args.reindex)

    if not args.question:
        print("Dùng: python -m bot.ask_cli \"deadline nộp bài tuần này là khi nào?\"")
        return

    engine = GeminiEngine(settings.gemini_api_key, settings.gemini_model)
    pipeline = AnswerPipeline(
        kb,
        engine,
        top_k=settings.top_k,
        similarity_threshold=settings.similarity_threshold,
    )
    result = pipeline.ask(args.question)
    print(pipeline.format_discord_reply(result, mentor_mention="@Mentor"))
    print("\n--- debug hits ---")
    for i, h in enumerate(result.hits):
        print(f"[{i}] sim={h['similarity']:.3f} source={h['source']}")
        print(h["text"][:180].replace("\n", " "))
        print()


if __name__ == "__main__":
    main()
