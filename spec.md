# Spec.md — Trợ lý học viên trên Discord (MVP, 1.5 ngày)

## 0. TL;DR cho team
Build 1 Discord bot đọc tin nhắn trong 1-2 channel, trả lời câu hỏi học viên dựa trên dữ liệu có sẵn (RAG), và khi không tự tin trả lời thì **tag đúng người phụ trách** thay vì im lặng hoặc trả lời bừa. Không cần quyền admin server — bot chỉ cần được invite và chỉ đọc tin nhắn **từ lúc được add trở đi**.

**Không làm gì thêm ngoài phạm vi này trong 1.5 ngày.** Mọi ý tưởng hay khác → note lại vào mục "Backlog / Nếu còn thời gian" ở cuối, không động vào lúc build.

---

## 1. Mục tiêu & phạm vi (Scope)

### Mục tiêu MVP
Chứng minh được 3 việc:
1. Bot trả lời đúng câu hỏi lặp lại, có trích dẫn nguồn.
2. Bot biết khi nào **không nên tự trả lời** và route đúng người.
3. Có 1 nơi (channel hoặc digest) để BTC/mentor thấy câu hỏi nào đang tồn đọng.

### Ngoài phạm vi (Out of scope cho 1.5 ngày)
- Không xử lý toàn bộ lịch sử chat cũ (tránh vướng quyền + tốn thời gian ingest/clean data)
- Không làm dashboard web riêng — dùng ngay Discord channel làm "dashboard"
- Không làm matching mentor bằng ML — dùng mapping thủ công (config file)
- Không làm reminder/escalate tự động phức tạp theo thời gian thực — làm bản rule đơn giản hoặc để vào backlog

---

## 2. User stories (ưu tiên theo P0 → P2)

| # | Priority | Story |
|---|---|---|
| 1 | P0 | Là học viên, tôi hỏi 1 câu trong channel, bot trả lời kèm link tới tin nhắn/tài liệu gốc nếu tìm thấy thông tin liên quan. |
| 2 | P0 | Là học viên, nếu bot không đủ tự tin trả lời, bot nói rõ "mình chưa chắc" và tag đúng mentor phụ trách chủ đề đó. |
| 3 | P1 | Là mentor/BTC, tôi có 1 channel riêng thấy được danh sách câu hỏi bot chưa trả lời được / đang chờ người xử lý. |
| 4 | P1 | Là học viên mới, khi tôi hỏi lần đầu trong channel, bot có thể gợi ý 1-2 tài liệu/channel bắt đầu phù hợp. |
| 5 | P2 | Là mentor, tôi nhận digest cuối ngày tổng hợp các câu hỏi hot/tồn đọng. |
| 6 | P2 (stretch) | Là mentor, khi có câu hỏi confidence thấp, tôi nhận **1 bản nháp câu trả lời do AI research sẵn** (không gửi thẳng cho học viên) — tôi có thể **chỉnh sửa/duyệt** trước khi gửi, thay vì phải tự soạn từ đầu. |

**Chốt cho demo:** Story 1, 2, 3 là bắt buộc. Story 4, 5, 6 làm nếu còn dư thời gian (xem mục Backlog, riêng Story 6 xem chi tiết ở mục 4.5).

---

## 3. Kiến trúc tổng quan

```
┌─────────────────┐
│  Discord Server  │
│  (channel FAQ /  │
│   thông báo)     │
└────────┬─────────┘
         │ message event (chỉ từ lúc bot join)
         ▼
┌─────────────────────┐
│   Discord Bot        │  discord.py hoặc discord.js
│  (listener + router)│
└────────┬─────────────┘
         │
    ┌────┴─────┐
    ▼          ▼
┌────────┐  ┌──────────────┐
│ Ingest  │  │ Query Handler │
│ pipeline│  │ (khi có câu   │
│ (embed  │  │  hỏi mới)     │
│ tin nhắn│  └──────┬───────┘
│ mới)    │         │
└────┬────┘         ▼
     │        ┌─────────────┐
     ▼        │ Vector DB    │◄────┐
┌─────────┐   │ (Chroma/     │     │
│ Vector DB│──►│ Supabase pg) │     │
└─────────┘   └──────┬───────┘     │
                      │ retrieve top-k
                      ▼
              ┌───────────────┐
              │ Gemini API     │
              │ (answer +      │
              │  confidence)   │
              └──────┬─────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
   confidence CAO           confidence THẤP
   → trả lời + nguồn        → reply "chưa chắc"
                             + tag mentor
                             + log vào #cần-hỗ-trợ
```

---

## 4. Luồng xử lý chi tiết

### 4.1 Ingest (nạp dữ liệu)
- Bot chỉ lắng nghe **tin nhắn mới** trong channel được chỉ định từ thời điểm bot online (không cần quyền đọc history cũ → tránh nút thắt quyền).
- Mỗi tin nhắn (trừ tin nhắn quá ngắn/emoji-only/của chính bot) được:
  1. Lưu raw text + metadata (author, timestamp, message link, channel)
  2. Embed và lưu vào Vector DB
- Nếu có sẵn tài liệu tĩnh (FAQ doc, file quy định) → nạp trước 1 lần lúc setup (seed data) để demo có dữ liệu ngay, không phải chờ tích lũy chat thật.

### 4.2 Query (khi học viên đặt câu hỏi)
1. Bot detect tin nhắn có dạng câu hỏi (đơn giản: kết thúc bằng "?", hoặc luôn xử lý mọi tin nhắn trong channel chỉ định — chọn cách nào dễ làm hơn trong 1.5 ngày)
2. Retrieve top-k chunk liên quan từ Vector DB
3. Gọi Gemini API với prompt gồm: câu hỏi + context retrieve được + yêu cầu model tự đánh giá confidence (VD: trả JSON `{answer, confidence: high/low, sources: [...]}`)
4. Nếu `confidence = high` → reply kèm nguồn (link tới message gốc)
5. Nếu `confidence = low` → reply ngắn gọn "Mình chưa tìm thấy thông tin chắc chắn, đã tag @mentor-phụ-trách giúp bạn nhé" + tag người phụ trách (theo mapping thủ công ở mục 4.3) + log câu hỏi vào channel `#cần-hỗ-trợ`

### 4.3 Routing (định tuyến người phụ trách)
- Dùng 1 file config đơn giản, KHÔNG cần AI, map từ khóa/chủ đề → Discord role hoặc user ID. Ví dụ:

```json
{
  "deploy,docker,server": "@mentor-devops",
  "model,training,fine-tune": "@mentor-ml",
  "điểm,chấm bài,deadline": "@ta-academic"
}
```
- Cách match đơn giản nhất cho 1.5 ngày: kiểm tra keyword xuất hiện trong câu hỏi hoặc trong câu trả lời của Gemini → chọn role tương ứng. Không cần ML phân loại phức tạp.
- Nếu không match keyword nào → tag role mặc định (VD `@mentor-oncall`).

### 4.4 "Dashboard" cho mentor (channel #cần-hỗ-trợ)
- Không build web dashboard. Mỗi câu hỏi confidence thấp → bot post vào channel riêng dạng:
```
❓ Câu hỏi từ @học_viên (link tới tin nhắn gốc)
Nội dung: "..."
Đã tag: @mentor-devops
Trạng thái: [ ] Chưa xử lý
```
- Mentor tự thả reaction ✅ khi đã trả lời xong (đủ để demo "trạng thái tồn đọng" mà không cần build gì thêm).

### 4.5 [STRETCH — chỉ làm nếu dư thời gian] Mentor Research Tool (AI soạn nháp, mentor duyệt trước khi gửi)

**Ý tưởng:** Thay vì bot chỉ tag mentor suông khi confidence thấp, bot sẽ **chủ động research và soạn sẵn 1 bản nháp câu trả lời**, gửi riêng cho mentor để mentor **đọc, chỉnh sửa (nếu cần), rồi bấm gửi** cho học viên — thay vì mentor phải tự gõ từ đầu. AI không bao giờ tự gửi thẳng câu trả lời cho học viên trong luồng này; mentor luôn là người quyết định cuối cùng.

**Vì sao đây là stretch, không phải core:** MVP core (Story 1-3) đã chứng minh được "AI biết khi nào nên/không nên tự trả lời". Story 6 là lớp nâng cao thêm cho mentor, không ảnh hưởng tới việc chứng minh ý tưởng chính — nên chỉ làm khi Story 1-3 đã chạy ổn định và còn dư thời gian thật sự (ước tính cần thêm 2-3 giờ).

**Luồng xử lý:**
1. Khi 1 câu hỏi rơi vào nhánh `confidence = low` (mục 4.2 bước 5), thay vì chỉ post "chưa chắc" cho học viên, bot **đồng thời** gửi 1 tin nhắn/DM riêng cho mentor được route tới, dạng:
```
🔍 Bản nháp trả lời cho câu hỏi của @học_viên
Câu hỏi: "..."
── Bản nháp AI research được ──
[nội dung AI soạn, kèm nguồn nếu có tìm được thông tin liên quan dù chưa đủ tự tin]
────────────────────────────
[✏️ Sửa & Gửi]   [✅ Gửi nguyên văn]   [❌ Bỏ qua, tự trả lời riêng]
```
2. Học viên **chưa nhận được gì** cho tới khi mentor xác nhận — tránh trường hợp AI trả lời sai trực tiếp cho học viên.
3. Mentor sửa nội dung (reply thẳng vào thread hoặc dùng lệnh đơn giản, tuỳ độ khó implement) → bot gửi bản đã duyệt vào channel gốc, trả lời đúng vào tin nhắn của học viên (giữ nguyên link nguồn/context).
4. Nếu mentor không phản hồi sau thời gian chờ (VD 1 câu hỏi vẫn hiện "chưa chắc" cho học viên như luồng gốc) → không block học viên chờ vô thời hạn.

**Yêu cầu kỹ thuật tối thiểu để làm được (nếu chọn làm):**
- Cách đơn giản nhất trong hackathon: bot gửi bản nháp bằng **DM hoặc thread riêng cho mentor**, mentor **reply lại đúng thread đó** với nội dung đã sửa (hoặc gõ nguyên văn nếu đồng ý bản nháp) → bot lấy nội dung reply đó và post vào channel gốc trả lời học viên. Không cần build UI nút bấm phức tạp (nút Discord button) nếu không đủ thời gian — reply bằng text là đủ để demo ý tưởng.
- Nếu dư thời gian hơn nữa mới cân nhắc làm Discord Buttons (`Sửa & Gửi` / `Gửi nguyên văn`) cho mượt UX.

**Điều kiện để bắt đầu làm Story 6:** Story 1, 2, 3 đã chạy ổn định và test qua ít nhất 1 lần end-to-end thành công. Nếu tới giờ 9 (theo timeline mục 7) mà core chưa ổn, **không động vào Story 6**.

---

## 5. Tech stack đề xuất (ưu tiên tốc độ dựng, không tối ưu)

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Bot framework | discord.py (Python) hoặc discord.js (Node) | Chọn theo ngôn ngữ team mạnh nhất, đừng học mới giữa hackathon |
| LLM | Gemini API (model Flash) | Có free tier, structured output tốt để trả JSON có confidence |
| Vector DB | Chroma (local, chạy trong process) | Không cần setup server riêng, nhanh nhất cho 1.5 ngày |
| Embedding | model embedding có sẵn qua API (hoặc sentence-transformers local nếu offline) | Tránh mất thời gian tự train |
| Hosting | Chạy local/máy cá nhân hoặc 1 VPS free tier (Railway/Render) | Chỉ cần chạy ổn định lúc demo, không cần production-grade |
| Config routing | 1 file JSON/YAML | Đơn giản, dễ sửa gấp trước demo |

---

## 6. Yêu cầu quyền & setup Discord (giải quyết trước, làm sớm nhất — giờ đầu tiên)

1. Tạo Discord Application + Bot trên [Discord Developer Portal](https://discord.com/developers/applications)
2. Bật **Message Content Intent** (Settings → Bot → Privileged Gateway Intents)
3. Tạo link invite với scope `bot` + permissions: `View Channel`, `Send Messages`, `Read Message History`, `Add Reactions`
4. **Gửi link invite cho admin/mod server học viện xin duyệt ngay từ đầu** — đây là việc phải làm sớm nhất vì phụ thuộc người khác phản hồi, không phải việc code.
5. Trong lúc chờ duyệt: dựng 1 server Discord test riêng, seed dữ liệu giả để build & test full flow không bị block.

---

## 7. Timeline đề xuất (1.5 ngày = ~12 giờ làm việc thực tế)

| Thời gian | Việc | Ai làm |
|---|---|---|
| Giờ 1 | Setup Discord app/bot, gửi xin quyền invite, tạo server test, chia việc | Cả team |
| Giờ 2–4 | Build bot listener + ingest pipeline + Vector DB cơ bản | Người A |
| Giờ 2–4 | Build prompt Gemini API (answer + confidence + sources dạng JSON) | Người B |
| Giờ 4–6 | Ghép query flow: retrieve → Gemini → reply có nguồn | Người A + B |
| Giờ 5–7 | Build routing config + logic tag mentor + post vào #cần-hỗ-trợ | Người C |
| Giờ 7–9 | Test end-to-end trên server test, seed thêm data thật (FAQ, thông báo cũ) | Cả team |
| Giờ 9–10 | Xin invite bot vào server thật (nếu đã được duyệt), test lại | Cả team |
| Giờ 10–11 | Sửa bug, polish message format, chuẩn bị các câu hỏi demo mẫu | Cả team |
| Giờ 11–12 | Làm slide/pitch, quay video demo backup (phòng lỗi mạng lúc demo live) | Cả team |

**Nguyên tắc:** nếu giờ 7 mà flow cơ bản (Story 1+2) chưa chạy được, cắt ngay Story 3 để dồn lực fix core flow. Không cắt Story 1+2 vì đó là phần chứng minh ý tưởng.

---

## 8. Kịch bản demo (chuẩn bị trước, không ứng biến)

1. Học viên hỏi 1 câu **có trong dữ liệu đã seed** (VD: "Deadline nộp project là khi nào?") → bot trả lời + link nguồn. *(chứng minh Story 1)*
2. Học viên hỏi 1 câu **ngoài phạm vi dữ liệu** (VD: "Làm sao fix lỗi CUDA out of memory?") → bot trả lời "chưa chắc" + tag đúng mentor devops/ml. *(chứng minh Story 2)*
3. Show channel `#cần-hỗ-trợ` có log câu hỏi #2 vừa rồi, mentor react ✅. *(chứng minh Story 3)*
4. (Nếu kịp) học viên mới join hỏi câu đầu tiên → bot gợi ý tài liệu bắt đầu.

Chuẩn bị sẵn 3–4 câu hỏi mẫu, test trước nhiều lần để chắc chắn không lỗi lúc pitch trực tiếp.

---

## 9. Rủi ro & phương án dự phòng

| Rủi ro | Phương án |
|---|---|
| Admin không duyệt invite bot kịp trước demo | Demo trên server test riêng với data seed giống thật |
| Gemini API confidence không ổn định / trả lời sai | Thêm rule cứng: nếu retrieve không có chunk nào similarity đủ cao → auto route, không cần chờ Gemini tự đánh giá |
| Bot lỗi/crash lúc demo live | Quay sẵn video demo backup, chạy song song |
| Dữ liệu chat thật quá ít để retrieve có ý nghĩa | Seed thêm FAQ/tài liệu tĩnh thủ công trước, không chỉ dựa vào chat tích lũy |

---

## 10. Backlog / Nếu còn thời gian (KHÔNG làm trước khi Story 1-3 chạy ổn)

Thứ tự ưu tiên nếu có dư thời gian (làm từ trên xuống, dừng bất cứ lúc nào hết giờ):
1. **Story 6 — Mentor Research Tool** (AI soạn nháp, mentor review & chỉnh sửa trước khi gửi cho học viên — chi tiết ở mục 4.5). Ưu tiên cao nhất trong backlog vì mở rộng trực tiếp từ core flow đã có (nhánh confidence thấp), không cần xây thêm hệ thống mới.
2. Story 4 (gợi ý onboarding cho học viên mới)
3. Story 5 (digest cuối ngày)
4. Escalate tự động nếu câu hỏi không ai xử lý sau X giờ
5. Phân quyền đọc dữ liệu theo channel nhạy cảm
6. Đo lường metrics (response time, số câu hỏi trùng lặp giảm) bằng số liệu thật thay vì ước lượng

---

## 11. Định nghĩa "Done" cho MVP
MVP được coi là hoàn thành khi: bot chạy ổn định trên server test/thật, trả lời đúng ít nhất 3 câu hỏi mẫu có nguồn trích dẫn, và route đúng ít nhất 2 câu hỏi mẫu ngoài phạm vi tới đúng mentor, có log hiển thị trong channel riêng — tất cả demo được liền mạch không cần giải thích thêm bằng lời.
