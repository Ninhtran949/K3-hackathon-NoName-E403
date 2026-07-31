from __future__ import annotations

import json
import re
from dataclasses import dataclass

from google import genai


ANSWER_PROMPT = """Bạn là trợ lý học viên của khoá AI Thực Chiến trên Discord.
Chỉ trả lời dựa trên CONTEXT bên dưới. Không bịa thông tin ngoài CONTEXT.
CONTEXT chỉ được lấy từ kênh Discord đã sync (nguồn dạng #tên-kênh) — không dùng file md/code.
Nếu CONTEXT không đủ để trả lời chắc chắn, đặt grounded=false.

Hiểu câu hỏi người dùng:
- Có thể gõ KHÔNG DẤU, viết tắt, sai chính tả, cú pháp lỏng (vd. "deadline nop bai khi nao", "nop muon bi tru bn").
- Diễn giải ý định trước khi đối chiếu CONTEXT; không yêu cầu câu hỏi phải đúng ngữ pháp.
- Nếu CONTEXT có mốc thời gian dạng [sent=YYYY-MM-DD ...]: 'mai' trong tin ngày D = D+1; quy về ngày tuyệt đối trước khi trả lời.

Quy tắc bắt buộc:
- Đòi đáp án lab/quiz/kiểm tra → grounded=false, từ chối ngắn, bảo hỏi Mentor/TA.
- Hỏi điểm cá nhân / API key / token → grounded=false, từ chối.
- Câu mơ hồ chung (vd. "nộp bài khi nào?" / "nop bai khi nao") → được trả quy tắc tuần thường trong CONTEXT + nêu rõ giả định.
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

    def decide_from_recent_chat(
        self,
        question: str,
        transcript: str,
        *,
        mode: str = "general",
    ) -> AIDecision:
        """Trả lời follow-up từ hội thoại gần đây (có username Discord)."""
        if not transcript.strip():
            return AIDecision(
                grounded=False,
                answer="Mình chưa tìm thấy tin nhắn phù hợp trong kênh này.",
                cite_indexes=[],
                best_similarity=0.0,
                raw="",
            )

        if mode == "user_messages":
            prompt = (
                "Bạn là trợ lý Discord. Người dùng hỏi về tin nhắn của MỘT người cụ thể.\n"
                "Transcript bên dưới CHỈ gồm tin của người đó (đã lọc).\n"
                "Mỗi dòng: [sent=... | ngày gửi=...] display_name (@username / id=...): nội dung\n"
                "Dòng đầu có NOW=... (giờ hiện tại UTC+7).\n\n"
                "QUY TẮC:\n"
                "- Liệt kê/tóm tắt những gì họ đã nhắn trong kênh, trung thực theo transcript.\n"
                "- Có thể gộp ý trùng; trích ngắn nội dung gốc nếu hữu ích.\n"
                "- Không bịa tin họ không gửi.\n"
                "- Nếu transcript trống / không có nội dung: grounded=false.\n"
                "- Trả lời tiếng Việt, ngắn gọn.\n\n"
                "Trả về ĐÚNG JSON (không markdown):\n"
                "{\n"
                '  "grounded": true/false,\n'
                '  "answer": "..."\n'
                "}\n\n"
                f"CÂU HỎI:\n{question.strip()}\n\n"
                f"TIN CỦA NGƯỜI ĐƯỢC HỎI:\n{transcript}"
            )
        elif mode == "temporal":
            prompt = (
                "Bạn là trợ lý Discord, giỏi suy luận thời gian tương đối.\n"
                "Transcript có NOW=... và mỗi tin có sent=YYYY-MM-DD HH:MM UTC+7.\n\n"
                "QUY TẮC THỜI GIAN BẮT BUỘC:\n"
                "- 'mai' / 'ngày mai' trong tin gửi ngày D nghĩa là ngày D+1.\n"
                "- 'hôm nay' / 'nay' trong tin gửi ngày D nghĩa là ngày D.\n"
                "- 'hôm qua' trong tin gửi ngày D nghĩa là ngày D-1.\n"
                "- Khi user hỏi 'nay/hôm nay ... mấy giờ': quy mọi mốc về ngày tuyệt đối, "
                "rồi chỉ trả lời mốc trùng NGÀY của NOW.\n"
                "- Ví dụ: tin ngày 30/7 nói 'mai đi học 8h' → sự kiện 31/7 08:00. "
                "Nếu NOW là 31/7 và hỏi 'nay đi học mấy giờ' → trả lời 8h "
                "(có thể nói rõ: hôm qua báo mai 8h = hôm nay 8h).\n"
                "- Nếu không có lịch nào khớp ngày đang hỏi → grounded=false, nói chưa thấy lịch cho ngày đó.\n"
                "- Không bịa. Chỉ dựa transcript.\n"
                "- Hiểu câu không dấu: 'nay di hoc may gio'.\n\n"
                "Trả về ĐÚNG JSON (không markdown):\n"
                "{\n"
                '  "grounded": true/false,\n'
                '  "answer": "câu trả lời ngắn tiếng Việt"\n'
                "}\n\n"
                f"CÂU HỎI:\n{question.strip()}\n\n"
                f"HỘI THOẠI (có timestamp):\n{transcript}"
            )
        else:
            prompt = (
                "Bạn là trợ lý Discord. Trả lời câu hỏi CHỈ dựa trên HỘI THOẠI GẦN ĐÂY bên dưới.\n"
                "Mỗi dòng có dạng: [sent=... | ngày gửi=...] display_name (@username / id=...): nội dung\n"
                "Dòng đầu có NOW=... (UTC+7).\n\n"
                "QUY TẮC BẮT BUỘC:\n"
                "- Hiểu đại từ: người đó, anh ấy, bạn ấy, người nói, account đó...\n"
                "- Suy luận thời gian: 'mai' trong tin ngày D = ngày D+1; "
                "khi hỏi 'hôm nay' so với NOW.\n"
                "- Nếu hỏi TÊN TÀI KHOẢN / username Discord:\n"
                "  * CHỈ lấy phần @username trong metadata dòng (giữa dấu ngoặc).\n"
                "  * CẤM lấy từ nội dung tin nhắn (vd. chữ 'mai tiến đi học' KHÔNG phải username).\n"
                "  * CẤM lấy display_name trừ khi user hỏi rõ 'tên hiển thị'.\n"
                "  * Trả lời dạng: Username Discord: `@username` (tên hiển thị: ...).\n"
                "- Nếu hỏi ai đó (@user / username) đã nhắn gì: chỉ dùng dòng của đúng người đó.\n"
                "- Không bịa. Không đủ căn cứ → grounded=false.\n"
                "- Không trả lời điểm cá nhân / API key / đáp án lab.\n"
                "- Nếu câu hỏi là deadline/FAQ mà hội thoại không đủ → grounded=false "
                "(để hệ thống dùng nguồn FAQ).\n\n"
                "Trả về ĐÚNG JSON (không markdown):\n"
                "{\n"
                '  "grounded": true/false,\n'
                '  "answer": "câu trả lời ngắn tiếng Việt"\n'
                "}\n\n"
                f"CÂU HỎI:\n{question.strip()}\n\n"
                f"HỘI THOẠI GẦN ĐÂY:\n{transcript}"
            )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        raw = (response.text or "").strip()
        parsed = _parse_json(raw)
        grounded = bool(parsed.get("grounded", False))
        answer = str(parsed.get("answer", "")).strip() or raw
        return AIDecision(
            grounded=grounded,
            answer=answer,
            cite_indexes=[],
            best_similarity=1.0 if grounded else 0.0,
            raw=raw,
        )

    def summarize_chat(self, transcript: str, *, focus: str = "") -> str:
        focus = focus.strip()
        if focus:
            prompt = (
                "Bạn là trợ lý Discord. Người dùng muốn tóm tắt theo MỘT trọng tâm cụ thể.\n"
                f"TRỌNG TÂM: {focus}\n\n"
                "QUY TẮC BẮT BUỘC:\n"
                "- CHỈ tóm tắt các câu/tin liên quan trực tiếp tới trọng tâm trên.\n"
                "- BỎ QUA hoàn toàn mọi chủ đề khác (deadline, thời tiết, dự án kỹ thuật, FAQ, tán gẫu… "
                "nếu không liên quan trọng tâm).\n"
                "- Không liệt kê chủ đề ngoài trọng tâm dù chúng có trong hội thoại.\n"
                "- Không bịa thông tin không có trong hội thoại.\n"
                "- Viết tiếng Việt, 3–7 gạch đầu dòng ngắn.\n"
                "- Nếu có: nêu việc cần làm / câu hỏi còn mở CHỈ về trọng tâm.\n"
                "- Nếu gần như không có tin nào liên quan trọng tâm: nói rõ "
                "\"Không thấy nội dung liên quan tới: <trọng tâm>\" và dừng, không tóm tắt phần khác.\n\n"
                f"HỘI THOẠI:\n{transcript}"
            )
        else:
            prompt = (
                "Bạn là trợ lý Discord. Hãy tóm tắt hội thoại bên dưới bằng tiếng Việt.\n"
                "Yêu cầu:\n"
                "- 5–10 gạch đầu dòng ngắn\n"
                "- Nêu quyết định / việc cần làm / câu hỏi còn mở (nếu có)\n"
                "- Không bịa nội dung không có trong hội thoại\n\n"
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
