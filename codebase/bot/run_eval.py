from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

from bot.config import load_settings
from bot.gemini_client import GeminiEngine
from bot.pipeline import AnswerPipeline
from bot.rag import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "eval" / "golden-set.json"
OUT = ROOT / "eval" / "results-round1.md"


def _fold(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def _contains_any(text: str, needles: list[str]) -> bool:
    if not needles:
        return True
    folded = _fold(text)
    return any(_fold(n) in folded for n in needles if n)


def _contains_none(text: str, needles: list[str]) -> bool:
    if not needles:
        return True
    folded = _fold(text)
    return all(_fold(n) not in folded for n in needles if n)


def judge(case: dict, grounded: bool, answer: str) -> tuple[bool, str]:
    notes: list[str] = []
    expect = case.get("expect_grounded")
    ok = True

    if expect is True and not grounded:
        ok = False
        notes.append("kỳ vọng grounded=true nhưng nhận false")
    elif expect is False and grounded:
        ok = False
        notes.append("kỳ vọng grounded=false nhưng nhận true (nguy cơ bịa)")

    must_any = case.get("must_include_any") or []
    # G13: chấp nhận grounded true HOẶC false nếu trả lời đúng hướng
    if case["id"] == "G13":
        if grounded:
            if not _contains_any(answer, ["23:59", "chủ nhật", "chu nhat", "cn"]):
                ok = False
                notes.append("G13 grounded nhưng thiếu quy tắc 23:59 CN")
        else:
            if not _contains_any(answer, must_any + ["chưa", "mentor", "hỏi lại", "tuần"]):
                # fallback mentor cũng chấp nhận
                notes.append("G13 không grounded — chấp nhận nếu không bịa ngày")
        # fail cứng nếu bịa ngày dạng DD/MM
        if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", answer):
            ok = False
            notes.append("G13 có vẻ bịa ngày cụ thể")
    else:
        if expect is True and must_any and not _contains_any(answer, must_any):
            ok = False
            notes.append(f"thiếu keyword kỳ vọng: {must_any}")
        if expect is False and must_any and not _contains_any(answer, must_any):
            # optional keywords for false cases
            pass

    if not _contains_none(answer, case.get("must_not_include_any") or []):
        ok = False
        notes.append("chứa nội dung cấm (bịa điểm/key/đáp án)")

    if ok and not notes:
        notes.append("ok")
    return ok, "; ".join(notes)


def ask_with_retry(pipeline: AnswerPipeline, question: str, *, retries: int = 6):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return pipeline.ask(question)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = 15 * (attempt + 1)
                # Parse "Please retry in Xs" if present
                m = re.search(r"retry in ([0-9.]+)s", msg, re.I)
                if m:
                    wait = max(wait, float(m.group(1)) + 1.5)
                print(f"  rate-limit, sleep {wait:.1f}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy golden set qua pipeline")
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--sleep", type=float, default=8.0, help="giãn cách gọi API (giây)")
    args = parser.parse_args()

    settings = load_settings()
    kb = KnowledgeBase(settings.kb_dir)
    if args.reindex:
        kb.reset()
        print("KB cleared. Hãy /sync_channels trên Discord rồi chạy lại eval (không seed md).")
        return
    removed = kb.purge_non_channel_sources()
    if removed:
        print(f"Purged {removed} file-based chunks")
    print(f"KB channel chunks: {kb.count()}")
    if kb.count() == 0:
        print("KB trống — chỉ trả lời từ kênh đã sync. Chạy /sync_channels trên bot trước.")
        return

    engine = GeminiEngine(settings.gemini_api_key, settings.gemini_model)
    pipeline = AnswerPipeline(
        kb,
        engine,
        top_k=settings.top_k,
        similarity_threshold=settings.similarity_threshold,
    )

    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    rows: list[dict] = []
    passed = 0

    for i, case in enumerate(cases, start=1):
        q = case["input"]
        print(f"[{i}/{len(cases)}] {case['id']}: {q[:70]}")
        try:
            result = ask_with_retry(pipeline, q)
            grounded = bool(result.decision.grounded)
            answer = result.decision.answer or ""
            reply = pipeline.format_discord_reply(result, mentor_mention="@Mentor")
            err = ""
        except Exception as exc:  # noqa: BLE001
            grounded = False
            answer = ""
            reply = f"ERROR: {type(exc).__name__}: {exc}"
            err = str(exc)

        ok, note = judge(case, grounded, answer if answer else reply)
        if err:
            ok = False
            note = f"exception: {err[:160]}"
        if ok:
            passed += 1

        rows.append(
            {
                "id": case["id"],
                "type": case.get("type", ""),
                "real": case.get("real", False),
                "input": q,
                "grounded": grounded,
                "pass": ok,
                "note": note,
                "output": reply[:500].replace("\n", " / "),
            }
        )
        time.sleep(max(0.0, args.sleep))

    total = len(cases)
    lines = [
        "# Kết quả chạy — vòng 1 (lần đầu)",
        "",
        f"- Model: `{settings.gemini_model}`",
        f"- Pass rate: **{passed}/{total}**",
        f"- Real-sourced cases: {sum(1 for c in cases if c.get('real'))}/{total}",
        "",
        "| id | kiểu | real? | grounded? | pass? | ghi chú | output (rút gọn) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['type']} | {r['real']} | {r['grounded']} | "
            f"{'PASS' if r['pass'] else 'FAIL'} | {r['note']} | {r['output'][:180]} |"
        )
    lines.append("")
    lines.append("## Failures")
    fails = [r for r in rows if not r["pass"]]
    if not fails:
        lines.append("_Không có._")
    else:
        for r in fails:
            lines.append(f"### {r['id']} FAIL")
            lines.append(f"- Input: `{r['input']}`")
            lines.append(f"- Note: {r['note']}")
            lines.append(f"- Output: {r['output']}")
            lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nDone: {passed}/{total} → {OUT}")


if __name__ == "__main__":
    main()
