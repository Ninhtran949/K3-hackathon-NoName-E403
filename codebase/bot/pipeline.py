from __future__ import annotations

from dataclasses import dataclass

from bot.gemini_client import AIDecision, GeminiEngine
from bot.rag import KnowledgeBase


@dataclass
class AnswerResult:
    decision: AIDecision
    hits: list[dict]
    sources: list[str]


class AnswerPipeline:
    def __init__(
        self,
        kb: KnowledgeBase,
        engine: GeminiEngine,
        *,
        top_k: int,
        similarity_threshold: float,
    ) -> None:
        self.kb = kb
        self.engine = engine
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def ask(self, question: str) -> AnswerResult:
        hits = self.kb.query(question, top_k=self.top_k)
        decision = self.engine.decide(
            question,
            hits,
            similarity_threshold=self.similarity_threshold,
        )
        sources: list[str] = []
        for i in decision.cite_indexes:
            h = hits[i]
            label = h.get("jump_url") or h.get("source") or f"chunk-{i}"
            if label not in sources:
                sources.append(label)
        if decision.grounded and not sources:
            for h in hits[:2]:
                label = h.get("jump_url") or h.get("source")
                if label and label not in sources:
                    sources.append(label)
        return AnswerResult(decision=decision, hits=hits, sources=sources)

    def format_discord_reply(
        self,
        result: AnswerResult,
        *,
        mentor_mention: str | None = None,
    ) -> str:
        d = result.decision
        if d.grounded:
            lines = [d.answer.strip()]
            if result.sources:
                lines.append("")
                lines.append("Nguồn:")
                for s in result.sources[:3]:
                    lines.append(f"- {s}")
            lines.append(f"_Độ tương đồng cao nhất: {d.best_similarity:.2f}_")
            return "\n".join(lines)

        mentor = mentor_mention or "Mentor/TA"
        return (
            f"{d.answer.strip()}\n\n"
            f"Câu hỏi này mình chưa đủ căn cứ để trả lời chắc. "
            f"{mentor} ơi, hỗ trợ giúp học viên với nhé!\n"
            f"_similarity={d.best_similarity:.2f} < ngưỡng_"
        )
