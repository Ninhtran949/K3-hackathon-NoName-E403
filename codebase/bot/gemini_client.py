from __future__ import annotations

import json
import re
from dataclasses import dataclass

from google import genai


ANSWER_PROMPT = """Bạn là trợ lý học viên của khoá AI Thực Chiến trên Discord.
Chỉ trả lời dựa trên CONTEXT bên dưới. Không bịa thông tin ngoài CONTEXT.
Nếu CONTEXT không đủ để trả lời chắc chắn, đặt grounded=false.

Quy tắc bắt buộc:
- Đòi đáp án lab/quiz/kiểm tra → grounded=false, từ chối ngắn, bảo hỏi Mentor/TA.
- Hỏi điểm cá nhân / API key / token → grounded=false, từ chối.
- Câu mơ hồ chung (vd. "nộp bài khi nào?" không nêu tuần) → được trả quy tắc tuần thường trong CONTEXT + nêu rõ giả định.
- Câu hỏi mốc CỤ THỂ mà CONTEXT không có (vd. tuần 99, midterm, buổi X chưa ghi) → grounded=false.
  KHÔNG được lấy quy tắc tuần thường rồi trả lời như thể đó là deadline của mốc đó.
- Không bịa deadline, link Zoom, điểm số.

Trả về ĐÚNG JSON (không markdown):
{{
  "grounded": true/false,
  "answer": "câu trả lời ngắn bằng tiếng Việt, hoặc giải thích vì sao chưa đủ căn cứ",
  "cite_indexes": [0, 1]
}}

CÂU HỎI:
{question}

CONTEXT (đánh số từ 0):
{context}
"""


@dataclass
class AIDecision:
    grounded: bool
    answer: str
    cite_indexes: list[int]
    best_similarity: float
    raw: str


class GeminiEngine:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def decide(
        self,
        question: str,
        hits: list[dict],
        similarity_threshold: float,
    ) -> AIDecision:
        best_sim = max((h["similarity"] for h in hits), default=0.0)
        if not hits or best_sim < similarity_threshold:
            return AIDecision(
                grounded=False,
                answer="Mình chưa tìm thấy căn cứ đủ chắc trong tài liệu/kênh kiến thức đã index.",
                cite_indexes=[],
                best_similarity=best_sim,
                raw="",
            )

        context_lines = []
        for i, h in enumerate(hits):
            context_lines.append(
                f"[{i}] source={h['source']} sim={h['similarity']:.2f}\n{h['text']}"
            )
        prompt = ANSWER_PROMPT.format(
            question=question.strip(),
            context="\n\n".join(context_lines),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        raw = (response.text or "").strip()
        parsed = _parse_json(raw)
        grounded = bool(parsed.get("grounded", False))
        answer = str(parsed.get("answer", "")).strip() or raw
        cites = parsed.get("cite_indexes") or []
        if not isinstance(cites, list):
            cites = []
        cites = [int(x) for x in cites if str(x).isdigit() or isinstance(x, int)]
        cites = [i for i in cites if 0 <= i < len(hits)]

        # Gate kép: similarity thấp HOẶC model bảo không grounded → fallback
        if best_sim < similarity_threshold:
            grounded = False
        return AIDecision(
            grounded=grounded,
            answer=answer,
            cite_indexes=cites,
            best_similarity=best_sim,
            raw=raw,
        )

    def summarize_chat(self, transcript: str, *, focus: str = "") -> str:
        focus_line = f"\nTrọng tâm người dùng muốn: {focus.strip()}" if focus.strip() else ""
        prompt = (
            "Bạn là trợ lý Discord. Hãy tóm tắt hội thoại bên dưới bằng tiếng Việt.\n"
            "Yêu cầu:\n"
            "- 5–10 gạch đầu dòng ngắn\n"
            "- Nêu quyết định / việc cần làm / câu hỏi còn mở (nếu có)\n"
            "- Không bịa nội dung không có trong hội thoại\n"
            f"{focus_line}\n\n"
            f"HỘI THOẠI:\n{transcript}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return (response.text or "").strip() or "Không tóm tắt được hội thoại này."


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"grounded": False, "answer": text, "cite_indexes": []}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"grounded": False, "answer": text, "cite_indexes": []}
