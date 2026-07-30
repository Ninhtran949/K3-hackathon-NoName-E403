from __future__ import annotations

import re
from dataclasses import dataclass

from bot.gemini_client import AIDecision, GeminiEngine
from bot.rag import KnowledgeBase, fold_vi

_MENTION_ID_RE = re.compile(r"<@!?(\d+)>")
_PLAIN_AT_RE = re.compile(r"@([A-Za-z0-9_\.]{2,32})")
_IDENTITY_RE = re.compile(
    r"(tên\s*tài\s*khoản|ten\s*tai\s*khoan|username|discord\s*tag|account|"
    r"người\s*(đó|này|ấy)|nguoi\s*(do|nay|ay)|ai\s*nói|ai\s*noi|người\s*nói|nguoi\s*noi|"
    r"nick(name)?|display\s*name|tên\s*user|ten\s*user)",
    re.IGNORECASE,
)
_USER_MSG_LOOKUP_RE = re.compile(
    r"(nh[aắ]n|noi|nói|gui|gửi|chat|viet|viết).{0,20}(g[iì]|j\b|gi\b)|"
    r"(đ[aã]|da).{0,12}(nh[aắ]n|noi|nói|gui|gửi)|"
    r"(cho\s*(tôi|toi|mình|minh)\s*biết|cho\s*biet).{0,40}(@|<@)|"
    r"(đã|da)\s*(nhắn|nhan|nói|noi|gửi|gui).{0,10}(gì|gi|j)",
    re.IGNORECASE,
)


def _is_identity_question(question: str) -> bool:
    q = question or ""
    return bool(_IDENTITY_RE.search(q) or _IDENTITY_RE.search(fold_vi(q)))


def _is_user_message_lookup(question: str) -> bool:
    q = question or ""
    folded = fold_vi(q)
    if _USER_MSG_LOOKUP_RE.search(q) or _USER_MSG_LOOKUP_RE.search(folded):
        return True
    # Có mention + hỏi về nội dung tin
    if _MENTION_ID_RE.search(q) and any(
        k in folded for k in ("nhan", "noi", "gui", "chat", "o day", "trong ken", "gi", " j")
    ):
        return True
    return False


def parse_mention_ids(text: str) -> list[int]:
    return [int(x) for x in _MENTION_ID_RE.findall(text or "")]


def parse_plain_ats(text: str) -> list[str]:
    """@username dạng chữ (chưa resolve thành <@id>)."""
    skip = {"neti", "everyone", "here", "bot"}
    out: list[str] = []
    for name in _PLAIN_AT_RE.findall(text or ""):
        low = name.lower()
        if low in skip:
            continue
        if low not in out:
            out.append(low)
    return out


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

    def ask(
        self,
        question: str,
        *,
        recent_chat: str = "",
        channel_label: str = "",
        target_user_chat: str = "",
        target_user_label: str = "",
    ) -> AnswerResult:
        # Hỏi "@user đã nhắn gì" → chỉ dùng tin của user đó
        if target_user_chat.strip() and _is_user_message_lookup(question):
            chat_decision = self.engine.decide_from_recent_chat(
                question,
                target_user_chat,
                mode="user_messages",
            )
            label = target_user_label or channel_label or "tin nhắn của người được hỏi"
            return AnswerResult(
                decision=chat_decision,
                hits=[],
                sources=[label] if chat_decision.grounded else [],
            )

        # Câu hỏi tên tài khoản / người nói: CHỈ dùng metadata hội thoại, không RAG FAQ
        if _is_identity_question(question) and recent_chat.strip():
            chat_decision = self.engine.decide_from_recent_chat(question, recent_chat)
            label = channel_label or "hội thoại gần đây trong kênh"
            return AnswerResult(
                decision=chat_decision,
                hits=[],
                sources=[label] if chat_decision.grounded else [],
            )

        hits = self.kb.query(question, top_k=self.top_k)
        # Chặn cứng: không bao giờ dùng file md/txt/code làm căn cứ
        hits = [
            h
            for h in hits
            if (h.get("source") or "").strip().startswith("#")
            and not (h.get("source") or "").lower().endswith((".md", ".txt", ".py"))
        ]
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

        # Follow-up khác: dùng hội thoại gần đây nếu RAG không đủ
        if not decision.grounded and recent_chat.strip():
            chat_decision = self.engine.decide_from_recent_chat(question, recent_chat)
            if chat_decision.grounded:
                label = channel_label or "hội thoại gần đây trong kênh"
                return AnswerResult(
                    decision=chat_decision,
                    hits=hits,
                    sources=[label],
                )

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
            # Chỉ hiện similarity khi trả lời từ RAG (không phải follow-up chat)
            from_chat = any(
                ("hội thoại gần đây" in (s or "")) or ("tin của @" in (s or "")) or ("tin nhắn của" in (s or ""))
                for s in result.sources
            )
            if not from_chat:
                lines.append(f"_Độ tương đồng cao nhất: {d.best_similarity:.2f}_")
            return "\n".join(lines)

        mentor = mentor_mention or "Mentor/TA"
        return (
            f"{d.answer.strip()}\n\n"
            f"Câu hỏi này mình chưa đủ căn cứ để trả lời chắc. "
            f"{mentor} ơi, hỗ trợ giúp học viên với nhé!\n"
            f"_similarity={d.best_similarity:.2f} < ngưỡng_"
        )
