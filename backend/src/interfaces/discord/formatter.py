"""Pure Discord response formatting without AI or persistence logic."""

from __future__ import annotations

from ...core_rag_engine.domain import (
    DigestResult,
    MentorDraft,
    ProcessingResult,
    ReviewDecisionResult,
)


def format_answer(result: ProcessingResult) -> str:
    lines = [result.answer.strip()]
    if result.sources:
        lines.extend(["", "**Nguồn:**"])
        for source in result.sources:
            if source.source_url:
                lines.append(f"- [{source.title}]({source.source_url})")
            else:
                lines.append(f"- `{source.title}`")
    lines.extend(_format_onboarding(result))
    return _truncate("\n".join(lines))


def format_escalation(result: ProcessingResult) -> str:
    mentor = result.mentor_mention or "mentor trực"
    lines = [
        "Mình chưa tìm thấy thông tin đủ chắc chắn để trả lời. "
        f"Đã tag {mentor} hỗ trợ bạn nhé."
    ]
    lines.extend(_format_onboarding(result))
    return _truncate("\n".join(lines))


def format_support_ticket(
    *,
    author_mention: str,
    question: str,
    source_url: str,
    mentor_mention: str,
    review_id: str = "",
    mentor_draft: MentorDraft | None = None,
) -> str:
    lines = [
        f"❓ **Câu hỏi từ {author_mention}** ([tin nhắn gốc]({source_url}))",
        f'**Nội dung:** "{question}"',
        f"**Đã tag:** {mentor_mention}",
        "**Trạng thái:** ⬜ Chờ mentor duyệt",
    ]
    if review_id:
        lines.extend(
            [
                f"**Review ID:** `{review_id}`",
                "",
                "**Lệnh trong thread:**",
                "- `!approve` — gửi nguyên bản nháp",
                "- `!send <nội dung>` — gửi bản mentor đã sửa",
                "- `!reject` — bỏ qua bản nháp",
            ]
        )
    lines.extend(["", "🔍 **Bản nháp AI — chưa gửi cho học viên:**"])
    if mentor_draft:
        lines.append(mentor_draft.text)
        if mentor_draft.sources:
            lines.append("**Nguồn tham khảo:**")
            for index, source in enumerate(mentor_draft.sources, start=1):
                if source.source_url:
                    lines.append(
                        f"- [{index}] [{source.title}]({source.source_url})"
                    )
                else:
                    lines.append(f"- [{index}] `{source.title}`")
        if mentor_draft.caveats:
            lines.append("**Mentor cần kiểm tra:**")
            lines.extend(f"- {caveat}" for caveat in mentor_draft.caveats)
    else:
        lines.append(
            "_Không tạo được bản nháp. Mentor vẫn có thể dùng "
            "`!send <nội dung>` để trả lời._"
        )
    return _truncate("\n".join(lines))


def format_approved_answer(result: ReviewDecisionResult) -> str:
    lines = ["✅ **Mentor đã duyệt:**", result.answer.strip()]
    if result.sources:
        lines.extend(["", "**Nguồn tham khảo:**"])
        for index, source in enumerate(result.sources, start=1):
            if source.source_url:
                lines.append(f"- [{index}] [{source.title}]({source.source_url})")
            else:
                lines.append(f"- [{index}] `{source.title}`")
    return _truncate("\n".join(lines))


def format_digest(result: DigestResult) -> str:
    lines = [
        f"📋 **Digest câu hỏi tồn đọng — {result.report_date}**",
        f"**Tổng số chưa xử lý:** {result.pending_count}",
    ]
    if not result.items:
        lines.extend(["", "🎉 Không có câu hỏi tồn đọng."])
        return "\n".join(lines)
    lines.append("")
    for index, item in enumerate(result.items, start=1):
        hot = f" — lặp {item.count} lần" if item.count > 1 else ""
        lines.append(
            f"{index}. [{item.question}]({item.source_url}){hot} "
            f"→ {item.mentor_mention}"
        )
    return _truncate("\n".join(lines))


def _truncate(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 15].rstrip() + "\n…(đã rút gọn)"


def _format_onboarding(result: ProcessingResult) -> list[str]:
    if not result.onboarding_suggestions:
        return []
    lines = [
        "",
        "👋 **Gợi ý bắt đầu dành cho lần hỏi đầu tiên của bạn:**",
    ]
    for suggestion in result.onboarding_suggestions:
        if suggestion.target.startswith(("https://", "http://")):
            lines.append(f"- [{suggestion.title}]({suggestion.target})")
        else:
            lines.append(f"- **{suggestion.title}:** {suggestion.target}")
    return lines
