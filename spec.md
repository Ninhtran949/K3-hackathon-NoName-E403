# Spec.md — Trợ lý học viên trên Discord (MVP, 1.5 ngày)

> Hướng B · Working prototype · Repo: `codebase/` · Eval: `eval/`

## 0. TL;DR cho team

Build Discord bot đọc FAQ/kênh kiến thức đã cấu hình, trả lời câu hỏi logistics học viên bằng RAG, và khi không đủ căn cứ thì **tag Mentor** + ghi Pending — không im lặng, không bịa deadline/link.

**Đã chốt lát cắt:** Học viên hỏi 1 câu → AI quyết định *có đủ căn cứ trong knowledge hay không* → trả lời + nguồn **hoặc** tag Mentor. Model: **`gemini-3.1-flash-lite`**.

**Không làm gì thêm ngoài phạm vi này trong 1.5 ngày.** Ý tưởng hay khác → mục 10 Backlog.

---

## 1. Mục tiêu & phạm vi (Scope)

### Mục tiêu MVP — chứng minh 3 việc

| # | Mục tiêu | Trạng thái nhóm |
|---|---|---|
| 1 | Bot trả lời đúng câu lặp lại (FAQ), có trích dẫn nguồn | **Done** — `/ask`, `@bot` + nguồn file/jump URL |
| 2 | Bot biết khi nào không nên tự trả lời → route Mentor | **Done** — gate kép similarity + `grounded=false` |
| 3 | Có chỗ BTC/mentor thấy câu hỏi tồn đọng | **Done (MVP)** — `/pending` + SQLite; escalate sau X giờ; `/digest` |

### Ngoài phạm vi (Out of scope cho 1.5 ngày)

- Không bắt buộc ingest toàn bộ lịch sử chat cũ (seed `knowledge/*.md` là đủ demo; `/sync_channels` là tùy chọn khi có quyền)
- Không làm dashboard web — dùng Discord (`/pending`, kênh hỏi đáp)
- Không matching mentor bằng ML — config `.env` (`MENTOR_USER_ID` / `MENTOR_ROLE_ID`)
- Không Mentor Research Tool (Story 6) trong MVP
- Không trả lời bài tập kỹ thuật sâu / đáp án lab

---

## 2. User stories (P0 → P2)

| # | Priority | Story | Trạng thái |
|---|---|---|---|
| 1 | P0 | Học viên hỏi → bot trả lời kèm nguồn nếu tìm thấy căn cứ | **Done** |
| 2 | P0 | Không đủ tự tin → nói chưa chắc + tag mentor | **Done** |
| 3 | P1 | Mentor thấy danh sách câu chưa trả lời được / đang chờ | **Done** — `/pending`, `/resolve` |
| 4 | P1 | Học viên mới hỏi lần đầu → gợi ý tài liệu/channel bắt đầu | **Backlog** |
| 5 | P2 | Digest cuối ngày / hàng đợi hot-tồn đọng | **Partial** — `/digest` on-demand (chưa cron daily) |
| 6 | P2 stretch | AI soạn nháp riêng cho mentor duyệt trước khi gửi HV | **Backlog** — không làm trước khi 1–3 ổn |

**Chốt demo:** Story 1, 2, 3 bắt buộc. 4–6 chỉ nếu dư thời gian.

---

## 3. Kiến trúc tổng quan (nhóm đã implement)

```
Discord (#hoi-dap / @bot / /ask)
         │
         ▼
   discord.py bot (listener + slash)
         │
    ┌────┴─────┐
    ▼          ▼
 Seed/sync    Query Handler
 knowledge/   (RAG retrieve)
 kênh FAQ          │
    │              ▼
    ▼        kb_store JSON
 Local KB    (TF-cosine top-k)
 (không Chroma trong MVP)
                   │
                   ▼
           Gemini API
           gemini-3.1-flash-lite
           JSON: grounded + answer + cites
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
 grounded=true           grounded=false
 → reply + nguồn         → "chưa chắc" + @Mentor
                         → SQLite Pending
                         → /pending · /digest · timeout escalate
```

**Lệch so với bản đề xuất form (có chủ đích, vì tốc độ hackathon):**

| Form đề xuất | Nhóm dùng | Lý do |
|---|---|---|
| Claude Sonnet | `gemini-3.1-flash-lite` | Key/quota sẵn; đủ JSON grounded |
| Chroma / embedding API | JSON local + TF cosine | Tránh phụ thuộc Chroma; demo ổn |
| Channel `#cần-hỗ-trợ` | `/pending` + DB | Đủ Story 3 không cần channel riêng |
| Mapping keyword nhiều mentor | 1 mentor mặc định (`.env`) | Đủ demo; multi-topic → backlog |

---

## 4. Luồng xử lý chi tiết

### 4.1 Ingest (nạp dữ liệu)

- **Seed tĩnh:** `codebase/knowledge/*.md` (FAQ logistics + policy) — nạp lúc bot start / `/reindex` / `ask_cli --reindex`.
- **Sync tùy chọn:** `/sync_channels` đọc lịch sử kênh trong `KNOWLEDGE_CHANNEL_IDS` (cần Message Content Intent + quyền đọc kênh).
- Mỗi chunk lưu text + source (+ jump_url nếu từ Discord).

### 4.2 Query (học viên hỏi)

1. Trigger: slash `/ask` hoặc `@bot <câu hỏi>` (có thể giới hạn `ASK_CHANNEL_ID`).
2. Retrieve top-k (`TOP_K=4`) từ KB local.
3. **Gate cứng:** nếu không hit hoặc `best_similarity < SIMILARITY_THRESHOLD` → auto `grounded=false`, không gọi model để bịa.
4. Nếu đủ similarity → gọi Gemini, bắt JSON `{grounded, answer, cite_indexes}`.
5. `grounded=true` → reply + nguồn; `false` → “chưa chắc” + tag Mentor + `Pending`.

**AI quyết định gì / model nào:**  
AI quyết định câu hỏi có đủ căn cứ trong knowledge để trả lời hay phải chuyển Mentor — dùng **`gemini-3.1-flash-lite`**. Chi tiết: `eval/ai-decision.md`.

### 4.3 Routing (định tuyến người phụ trách)

Hiện tại (MVP):

```
MENTOR_USER_ID=<discord user>   # ưu tiên
MENTOR_ROLE_ID=<role>           # fallback
```

Backlog (đúng form keyword map):

```json
{
  "deploy,docker,server": "@mentor-devops",
  "model,training,fine-tune": "@mentor-ml",
  "điểm,chấm bài,deadline": "@ta-academic",
  "_default": "@mentor-oncall"
}
```

### 4.4 "Dashboard" mentor

- `/pending` — list Pending/Escalated  
- `/resolve id:` — đóng sau khi mentor trả lời  
- Cron 15 phút: Pending > `PENDING_TIMEOUT_HOURS` → nhắc + đánh dấu Escalated  
- (Stretch UX) reaction ✅ trên post `#cần-hỗ-trợ` — backlog nếu tạo channel riêng

### 4.5 [STRETCH] Mentor Research Tool

**Không làm trong MVP hiện tại.** Chỉ mở khi Story 1–3 đã e2e ổn và còn ≥2–3 giờ. Luồng ý tưởng giữ như form gốc (nháp riêng mentor → duyệt → mới gửi HV).

---

## 5. Tech stack thực tế

| Thành phần | Lựa chọn | Ghi chú |
|---|---|---|
| Bot | `discord.py` + slash commands | `codebase/bot/main.py` |
| LLM | Gemini `gemini-3.1-flash-lite` | `google-genai` |
| KB / retrieve | JSON + TF cosine | `bot/rag.py`, thư mục `kb_store/` |
| State Pending | SQLite + `aiosqlite` | Pending / Resolved / Escalated |
| Config | `.env` | token, guild, mentor, threshold |
| Eval | `bot/run_eval.py` + `eval/golden-set.json` | đo precision-first |
| Hosting demo | máy local | đủ pitch |

---

## 6. Quyền & setup Discord (làm sớm)

1. Discord Application → Bot → bật **Message Content Intent**
2. Invite: scopes `bot` + `applications.commands`
3. Permissions: View Channel, Send Messages, Read Message History, (Mention nếu tag role)
4. Điền `.env`: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `GEMINI_API_KEY`, `MENTOR_USER_ID`, optional `KNOWLEDGE_CHANNEL_IDS` / `ASK_CHANNEL_ID`
5. Server test riêng + seed `knowledge/` để không bị block chờ invite server thật

---

## 7. Timeline (đã / còn lại)

| Mốc | Việc | Trạng thái |
|---|---|---|
| Setup bot + `.env` + server test | Quyền + invite | Đã có bot chạy |
| Listener + ingest + KB | Seed FAQ | Done |
| Prompt grounded JSON | Gemini decide | Done |
| Query flow retrieve → reply | `/ask`, `@bot` | Done |
| Routing + Pending + digest | tag mentor, `/pending`, `/digest`, timeout | Done (MVP) |
| Golden set ≥20 + chạy đo | `eval/` | Done — **22/22** lần gần nhất |
| Polish demo + slide + video backup | Pitch | Việc team còn lại |

**Nguyên tắc giữ nguyên form:** nếu core Story 1+2 lỗi → cắt tính năng phụ, không cắt 1+2.

---

## 8. Kịch bản demo (chuẩn bị sẵn)

1. **Story 1:** `deadline nộp bài khi nào?` → 23:59 CN + nguồn `faq_logistics.md`
2. **Story 2:** `API key Gemini của lớp là gì?` hoặc `đáp án lab 1` → chưa chắc + @Mentor + Pending
3. **Story 3:** `/pending` hiện câu vừa rồi; mentor `/resolve`
4. (Nếu kịp) `/digest` — tóm tắt hàng đợi

Câu mẫu thêm: Zoom ở đâu · nộp muộn trừ bao nhiêu · tuần 99 (phải *không* bịa).

---

## 9. Rủi ro & dự phòng

| Rủi ro | Phương án |
|---|---|
| Admin chưa duyệt invite | Demo server test + seed FAQ |
| Gemini 429 / hết quota | Đổi model trong `.env`; gate similarity vẫn chặn bịa; CLI `ask_cli` / `run_eval` |
| Confidence/grounded lệch | Gate cứng similarity; golden set bắt `grounded=false` khi thiếu căn cứ |
| Crash lúc live | Video demo backup; chạy CLI song song |
| Chat thật ít | Seed `knowledge/` — không phụ thuộc chat tích lũy |

---

## 10. Backlog / Nếu còn thời gian

Thứ tự (chỉ sau khi 1–3 ổn):

1. Story 6 — Mentor Research Tool (nháp duyệt trước khi gửi HV)
2. Story 4 — onboarding gợi ý channel/tài liệu
3. Story 5 — digest cron cuối ngày (hiện chỉ `/digest` tay)
4. Keyword → nhiều mentor (`routing.json`)
5. Channel `#cần-hỗ-trợ` + reaction ✅
6. Metrics: response time, % câu escalate, trùng lặp

---

## 11. Định nghĩa "Done" cho MVP

MVP xong khi:

- [x] Bot chạy trên server test/thật
- [x] ≥3 câu FAQ trả lời đúng có nguồn (đã cover trong golden set G01–G05, G10…)
- [x] ≥2 câu ngoài phạm vi route Mentor (G06, G07, G15…)
- [x] Mentor xem được tồn đọng (`/pending`)
- [x] Demo liền mạch không cần giải thích thêm bằng lời (kịch bản mục 8)

**Kiểm thử chất lượng (bắt buộc hackathon):**

- Chiều: precision-first (không bịa) > coverage  
- Golden set: `eval/golden-set.md` + `eval/golden-set.json` (23 case; ≥2 mỗi lớp chỗ khó; **10 real**).
- Kết quả **lần đầu**: **13/22** — `eval/results-round1.md` (nhiều FAIL do 429 quota)
- Vòng sau: **22/22** — `eval/results-round2.md`
- Quality bar (chốt, không hạ): **≥70% câu thử đạt, và không được trả lời sai / bịa deadline lần nào.**

### 4 lớp chỗ khó (map golden set)

| Lớp | Hành vi mong muốn | Ví dụ case |
|---|---|---|
| ① Thiếu trong tài liệu | Không bịa; escalate | G08 tuần 99, G11 midterm |
| ② Mơ hồ / thiếu ngữ cảnh | Giả định rõ hoặc hỏi lại / escalate | G13, G14, G21 |
| ③ Không được phép | Từ chối + Mentor | G06 điểm, G07 key, G15 đáp án |
| ④ Hậu quả thật nếu sai | Precision cao, có nguồn | G01 deadline, G04 Zoom, G17 muộn |

---

## 12. Changelog

| Thời điểm | Đổi gì | Vì sao |
|---|---|---|
| MVP day1 | Scaffold Discord + RAG local + Gemini grounded | Chốt lát cắt Hướng B |
| MVP day1 | `/pending` `/resolve` `/digest` + timeout | Đủ Story 3 + signal nhẹ |
| Eval | Golden 22 case; sửa prompt G08 + FAQ Zoom G04 | Pass bar; tránh bịa mốc cụ thể |
| Spec | Viết lại theo form MVP 1.5 ngày | Khớp code thật (Gemini, không Chroma) |
