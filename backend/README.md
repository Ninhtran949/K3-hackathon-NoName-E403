# K3 Mate Backend

Discord Student Assistant triển khai Story 1–6 bằng Python, Gemini, ChromaDB và
sentence-transformers theo Clean Architecture / Ports & Adapters.

## Trạng thái MVP

- Story 1: trả lời câu hỏi có căn cứ và liệt kê nguồn.
- Story 2: retrieval/confidence thấp thì không đoán, tag mentor theo keyword.
- Story 3: ghi escalation vào text channel hoặc tạo post trong Discord Forum.
- Story 4: câu hỏi đầu tiên của mỗi học viên trong từng channel nhận tối đa 2
  gợi ý tài liệu/channel phù hợp; trạng thái được lưu bền vững bằng SQLite.
- Story 5: digest cuối ngày nhóm câu hỏi trùng và liệt kê ticket còn pending.
- Story 6: Gemini soạn bản nháp riêng trong support thread; mentor phải duyệt,
  sửa hoặc từ chối trước khi bot gửi về đúng tin nhắn học viên.
- Static seed và tin nhắn Discord mới đều có thể được ingest.
- Unit/integration tests không cần gọi mạng; E2E đã chạy trên Discord test server.

## Luồng xử lý

```text
Discord event
    -> interfaces/discord (parse + format)
        -> CoreRAGEngine inbound API
            -> embedding port -> sentence-transformers
            -> vector-store port -> ChromaDB
            -> LLM port -> Gemini structured JSON
            -> routing port -> configs/routing.yaml
            -> activity port -> SQLite first-question state
            -> onboarding port -> configs/onboarding.yaml
            -> draft port -> Gemini 2.5 + Google Search Grounding
            -> support repository -> SQLite review/digest state
        -> SupportWorkflow inbound API
            -> mentor approval state machine
            -> daily unresolved digest
        -> Discord reply / support ticket
```

Discord adapter không import hay điều phối Gemini, ChromaDB hoặc embedding.
Dependency được nối duy nhất tại `src/bootstrap/container.py`.

## Cấu trúc chính

```text
backend/
|-- .env.example
|-- requirements.txt
|-- pytest.ini
|-- configs/
|   |-- app.yaml
|   |-- onboarding.yaml
|   `-- routing.yaml
|-- prompts/
|   |-- mentor_draft.md
|   `-- rag_answer.md
|-- data/
|   |-- chroma/
|   |-- state/
|   `-- seed/
|       `-- demo_faq.json
|-- scripts/
|   |-- reset_onboarding.py
|   `-- seed.py
|-- src/
|   |-- bootstrap/
|   |   |-- settings.py
|   |   |-- container.py
|   |   `-- main.py
|   |-- interfaces/
|   |   `-- discord/
|   `-- core_rag_engine/
|       |-- domain/
|       |-- application/
|       |-- ports/
|       `-- adapters/outbound/
`-- tests/
    |-- unit/
    `-- integration/
```

## Cài đặt

Yêu cầu Python 3.11:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Điền các giá trị Discord/Gemini trong `.env`; không commit file này.

## Cấu hình Discord

Bot cần bật `Message Content Intent` và có các quyền:

- View Channel
- Send Messages
- Read Message History
- Add Reactions
- Create Public Threads
- Send Messages in Threads

`DISCORD_MONITORED_CHANNEL_IDS` nhận một hoặc nhiều ID, phân tách bằng dấu phẩy.
`DISCORD_SUPPORT_CHANNEL_ID` có thể trỏ tới text channel hoặc Forum Channel.

Mentor được cấu hình tại `configs/routing.yaml`:

```yaml
default:
  mentor_mention: "<@USER_ID>"
```

Hoặc dùng role mention: `<@&ROLE_ID>`.

Gợi ý dành cho câu hỏi đầu tiên được cấu hình tại
`configs/onboarding.yaml`. Hai placeholder `{monitored_channels}` và
`{support_channel}` tự lấy ID từ `.env`, vì vậy không cần hard-code channel ID
vào YAML. State được lưu tại `ONBOARDING_STATE_DB_PATH`.

Review/digest state được lưu tại `SUPPORT_STATE_DB_PATH`. Lịch digest nằm trong
`configs/app.yaml`, mặc định `23:00 Asia/Bangkok`. Prompt bản nháp mentor nằm
riêng tại `prompts/mentor_draft.md`.

`GEMINI_MODEL` dùng cho RAG answer có structured output.
`MENTOR_RESEARCH_MODEL` mặc định là `gemini-2.5-flash` và chỉ dùng cho nhánh
confidence thấp có Google Search Grounding. Cả hai dùng chung `GEMINI_API_KEY`.

## Seed dữ liệu

Bot tự seed khi khởi động nếu `SEED_ON_STARTUP=true`. Có thể seed thủ công:

```powershell
python -m scripts.seed
```

Loader hỗ trợ JSON, Markdown và TXT trong `data/seed`. Tin nhắn mới không kết
thúc bằng `?` trong channel được theo dõi cũng được ingest và giữ
`message.jump_url` làm citation.

## Chạy bot

```powershell
python -m src.bootstrap.main
```

Khi thấy log dưới đây, bot đã sẵn sàng:

```text
Discord bot ready as K3 Mate...
```

## Chạy test

```powershell
python -m pytest
python -m pip check
```

Test offline bao phủ:

- ingest message mới;
- trả lời high-confidence có citation;
- hard threshold không gọi LLM khi retrieval thấp;
- downgrade câu trả lời không có citation;
- keyword routing và fallback;
- onboarding theo keyword, giới hạn số gợi ý và fallback;
- trạng thái first-question còn nguyên sau khi adapter SQLite khởi tạo lại;
- authorization và state machine duyệt/retry/reject bản nháp;
- nhóm câu hỏi hot và chống gửi lặp digest trong cùng ngày;
- Discord formatting;
- ChromaDB round-trip.

## Kịch bản demo Story 1–6

Trong monitored channel:

1. Hỏi `Bot Discord cần những quyền nào?`
2. Bot trả lời kèm nguồn `spec.md §6`.
3. Hỏi `Làm sao fix lỗi CUDA out of memory?`
4. Bot trả confidence thấp, tag mentor.
5. Mở forum hỗ trợ và kiểm tra ticket có bản nháp AI, Review ID và danh sách
   nguồn web `[1]`, `[2]` lấy trực tiếp từ Gemini grounding metadata.
6. Trong đúng forum thread, mentor chọn một lệnh:

   - `!approve`: gửi nguyên bản nháp;
   - `!send Nội dung mentor đã sửa`: gửi bản đã chỉnh sửa;
   - `!reject`: bỏ qua bản nháp.

7. Kiểm tra bot reply đúng tin nhắn học viên và review chuyển sang `sent`.
8. Trong một support thread, nhập `!digest` để tạo digest ngay; lịch tự động
   vẫn chạy lúc 23:00.
9. Dùng một tài khoản chưa từng hỏi trong channel để gửi câu hỏi đầu tiên; bot
   sẽ thêm khối `Gợi ý bắt đầu` vào chính reply.

Để chạy lại Story 4 bằng cùng một tài khoản, bật Developer Mode trong Discord,
copy User ID và Channel ID rồi reset đúng một marker:

```powershell
python -m scripts.reset_onboarding `
  --author-id YOUR_USER_ID `
  --channel-id YOUR_CHANNEL_ID
```

Sau đó gửi một câu hỏi mới có dấu `?` ở cuối.

Nếu support channel không tạo được thread, dùng Review ID hiển thị trong ticket:

```text
!approve REVIEW_ID
!send REVIEW_ID | Nội dung mentor đã sửa
!reject REVIEW_ID
```

Muốn demo citation Discord thật, post trước một câu khẳng định không có dấu `?`,
sau đó hỏi lại nội dung đó bằng một message mới.

## Quy tắc an toàn

- Không có chunk đạt `minimum_similarity` thì không gọi Gemini và luôn escalate.
- Gemini chỉ được trả high-confidence khi cung cấp source ID hợp lệ.
- API lỗi, JSON lỗi hoặc câu trả lời không có citation đều tự động escalate.
- Bản nháp confidence thấp không bao giờ tự gửi; chỉ mentor đúng role hoặc người
  có quyền Manage Messages mới duyệt được.
- Mentor draft chỉ được tạo khi Gemini trả ít nhất một `groundingChunk`; response
  không có nguồn web bị từ chối thay vì giả vờ đã research.
- Inline citation dùng `groundingSupports`; tiêu đề và URL nguồn dùng
  `groundingChunks`.
- Gửi bản duyệt lỗi sẽ đưa review từ `sending` quay lại `pending` để thử lại.
- Luồng trả lời học viên chỉ dùng chunk vượt hard threshold; bản nháp mentor có
  thể xem top-k context yếu nhưng luôn ghi caveat và bắt buộc human review.
- Không tự động ingest data pack riêng của hackathon.
