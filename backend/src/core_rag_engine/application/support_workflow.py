"""Mentor review and unresolved-question digest use cases."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from ..domain import (
    DigestItem,
    DigestResult,
    EscalationRecord,
    MentorDecisionInput,
    ReviewAction,
    ReviewDecisionKind,
    ReviewDecisionResult,
)
from ..ports.outbound import SupportRepositoryPort


@dataclass(frozen=True, slots=True)
class SupportWorkflowConfig:
    digest_enabled: bool = True
    digest_timezone: str = "Asia/Bangkok"
    digest_hour: int = 23
    digest_minute: int = 0
    digest_maximum_items: int = 10
    digest_poll_seconds: int = 60
    maximum_approved_answer_length: int = 1600


class SupportWorkflow:
    """Application service for human approval and daily digests."""

    def __init__(
        self,
        repository: SupportRepositoryPort,
        config: SupportWorkflowConfig,
    ) -> None:
        self._repository = repository
        self._config = config
        self._timezone = ZoneInfo(config.digest_timezone)
        self._scheduled_time = time(
            hour=config.digest_hour,
            minute=config.digest_minute,
        )
        if config.digest_maximum_items <= 0:
            raise ValueError("digest_maximum_items must be positive")
        if config.maximum_approved_answer_length <= 0:
            raise ValueError("maximum_approved_answer_length must be positive")

    @property
    def digest_poll_seconds(self) -> int:
        return max(10, self._config.digest_poll_seconds)

    def bind_review_context(
        self,
        review_id: str,
        support_context_id: str,
    ) -> bool:
        if not review_id or not support_context_id:
            return False
        return self._repository.bind_context(review_id, support_context_id)

    def decide(self, decision: MentorDecisionInput) -> ReviewDecisionResult:
        record = self._repository.find(
            review_id=decision.review_id,
            support_context_id=decision.support_context_id,
        )
        if record is None:
            return self._result(
                ReviewDecisionKind.NOT_FOUND,
                "Không tìm thấy review đang chờ trong thread này.",
            )

        status = self._repository.status(record.review_id)
        if status != "pending":
            return self._result(
                ReviewDecisionKind.ALREADY_RESOLVED,
                f"Review `{record.review_id}` đã ở trạng thái `{status}`.",
                record,
            )
        if not self._is_authorized(decision, record):
            return self._result(
                ReviewDecisionKind.UNAUTHORIZED,
                "Bạn không thuộc mentor được tag và không có quyền quản lý tin nhắn.",
                record,
            )

        if decision.action is ReviewAction.REJECT:
            if not self._repository.mark_rejected(record.review_id):
                return self._result(
                    ReviewDecisionKind.ALREADY_RESOLVED,
                    "Review vừa được một mentor khác xử lý.",
                    record,
                )
            return self._result(
                ReviewDecisionKind.REJECTED,
                "Đã bỏ qua bản nháp. Ticket được đánh dấu rejected.",
                record,
            )

        answer = (
            record.draft.text.strip()
            if decision.action is ReviewAction.APPROVE and record.draft
            else decision.edited_answer.strip()
        )
        if not answer:
            return self._result(
                ReviewDecisionKind.INVALID,
                "Không có nội dung để gửi. Dùng `!send <nội dung đã sửa>`.",
                record,
            )
        if len(answer) > self._config.maximum_approved_answer_length:
            return self._result(
                ReviewDecisionKind.INVALID,
                "Bản trả lời quá dài; hãy rút gọn trước khi gửi.",
                record,
            )
        if not self._repository.claim_for_delivery(record.review_id):
            return self._result(
                ReviewDecisionKind.ALREADY_RESOLVED,
                "Review vừa được một mentor khác xử lý.",
                record,
            )
        return ReviewDecisionResult(
            kind=ReviewDecisionKind.READY_TO_SEND,
            message="Bản trả lời đã được duyệt và sẵn sàng gửi.",
            review_id=record.review_id,
            answer=answer,
            original_channel_id=record.original_channel_id,
            original_message_id=record.original_message_id,
            sources=record.draft.sources if record.draft else (),
        )

    def complete_delivery(self, review_id: str, succeeded: bool) -> None:
        if succeeded:
            self._repository.mark_sent(review_id)
        else:
            self._repository.restore_pending(review_id)

    def build_digest(
        self,
        now: datetime,
        *,
        force: bool = False,
    ) -> DigestResult | None:
        local_now = now.astimezone(self._timezone)
        report_date = local_now.date().isoformat()
        if not force:
            if not self._config.digest_enabled:
                return None
            if local_now.time() < self._scheduled_time:
                return None
            if self._repository.last_digest_date() == report_date:
                return None

        records = tuple(self._repository.list_pending(limit=1000))
        grouped: dict[str, list[EscalationRecord]] = defaultdict(list)
        for record in records:
            grouped[self._normalize_question(record.question)].append(record)

        items = [
            DigestItem(
                question=group[0].question,
                count=len(group),
                oldest_at=min(record.created_at for record in group),
                source_url=group[0].source_url,
                mentor_mention=group[0].mentor_mention,
            )
            for group in grouped.values()
        ]
        items.sort(key=lambda item: (-item.count, item.oldest_at))
        return DigestResult(
            report_date=report_date,
            pending_count=len(records),
            items=tuple(items[: self._config.digest_maximum_items]),
        )

    def mark_digest_sent(self, report_date: str) -> None:
        self._repository.mark_digest_sent(report_date)

    @staticmethod
    def _is_authorized(
        decision: MentorDecisionInput,
        record: EscalationRecord,
    ) -> bool:
        if decision.can_moderate:
            return True
        role_match = re.fullmatch(r"<@&(\d+)>", record.mentor_mention)
        if role_match:
            return role_match.group(1) in decision.reviewer_role_ids
        user_match = re.fullmatch(r"<@!?(\d+)>", record.mentor_mention)
        return bool(user_match and user_match.group(1) == decision.reviewer_id)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(re.findall(r"\w+", question.casefold()))

    @staticmethod
    def _result(
        kind: ReviewDecisionKind,
        message: str,
        record: EscalationRecord | None = None,
    ) -> ReviewDecisionResult:
        return ReviewDecisionResult(
            kind=kind,
            message=message,
            review_id=record.review_id if record else "",
        )
