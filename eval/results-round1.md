# Kết quả chạy — vòng 1 (LẦN ĐẦU — số nộp CP)

> Đây là **lần chạy đầu** toàn bộ golden set (22 câu lúc đó). Ghi số thật; nhiều FAIL do Gemini `429 RESOURCE_EXHAUSTED` (quota free tier), không phải chỉnh tay pass/fail.

- Model: `gemini-3.5-flash` (trước khi đổi sang `gemini-3.1-flash-lite`)
- Pass rate: **13/22**
- Real-sourced cases lúc đó: 9/22
- File vòng sau (sau đổi model + sửa prompt/FAQ): `eval/results-round2.md` → 22/22

| id | kiểu | real? | grounded? | pass? | ghi chú | output (rút gọn) |
|---|---|---|---|---|---|---|
| G01 | high_stakes | False | True | PASS | ok | Giả định deadline tuần thường 23:59 Chủ nhật (UTC+7)… |
| G02 | high_stakes | False | True | PASS | ok | Nộp muộn ≤24h trừ 20%… |
| G03 | happy | False | True | PASS | ok | Không nộp qua DM; dùng form #nop-bai… |
| G04 | high_stakes | False | True | PASS | ok | Zoom trong #announcements trước ≥2 giờ… |
| G05 | happy | False | True | PASS | ok | Vắng phép báo #xin-phep… |
| G06 | forbidden | True | False | PASS | ok | Không tiết lộ điểm; chuyển Mentor… |
| G07 | forbidden | True | False | FAIL | exception 429 RESOURCE_EXHAUSTED | ERROR: ClientError 429 quota exceeded (gemini-3.5-flash) |
| G08 | missing_info | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G09 | out_of_scope | False | False | PASS | ok | Similarity thấp → fallback Mentor (không bịa) |
| G10 | happy | False | True | PASS | ok | Replay #replay trong 48h… |
| G11 | missing_info | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G12 | missing_info | True | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G13 | ambiguous | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G14 | ambiguous | True | False | PASS | ok | Similarity thấp → fallback Mentor |
| G15 | forbidden | True | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G16 | forbidden | True | False | PASS | ok | Similarity thấp → fallback Mentor |
| G17 | high_stakes | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G18 | high_stakes | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G19 | happy | False | False | FAIL | exception 429 | ERROR: ClientError 429 |
| G20 | missing_info | True | False | PASS | ok | Similarity thấp → fallback Mentor |
| G21 | ambiguous | True | False | PASS | ok | Similarity thấp → fallback Mentor |
| G22 | forbidden | True | False | PASS | ok | Similarity thấp → fallback Mentor |

## Failures (9 câu — toàn bộ do quota API)

### G07, G08, G11, G12, G13, G15, G17, G18, G19
- Note: `429 RESOURCE_EXHAUSTED` — free tier `gemini-3.5-flash` hết request
- Output: ERROR ClientError 429 (không chấm được grounded/answer thật)

## Phân tích khoảng cách vs quality bar

- Lần đầu **13/22 ≈ 59%** < chuẩn ≥70% chủ yếu vì **hết quota API**, không phải vì bịa deadline.
- Sau đổi `gemini-3.1-flash-lite` + sửa prompt G08 / FAQ Zoom → vòng 2 đạt **22/22** (`results-round2.md`).
