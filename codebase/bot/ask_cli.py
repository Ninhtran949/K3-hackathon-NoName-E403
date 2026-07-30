from __future__ import annotations

import argparse

from bot.config import load_settings
from bot.gemini_client import GeminiEngine
from bot.pipeline import AnswerPipeline
from bot.rag import KnowledgeBase


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI test RAG — chỉ dùng KB kênh Discord đã sync (không đọc md)"
    )
    parser.add_argument("question", nargs="?", help="Câu hỏi")
    parser.add_argument(
        "--purge-files",
        action="store_true",
        help="Xoá chunk nguồn file md/txt còn sót trong KB",
    )
    args = parser.parse_args()

    settings = load_settings()
    kb = KnowledgeBase(settings.kb_dir)
    if args.purge_files:
        n = kb.purge_non_channel_sources()
        print(f"Purged {n} non-channel chunks")
    print(f"KB channel chunks: {kb.count()} (chỉ #kênh Discord — chạy /sync_channels trên bot)")

    if not args.question:
        print('Dùng: python -m bot.ask_cli "deadline nộp bài khi nào?"')
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
