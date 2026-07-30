# Spec v2 — Trợ lý AI cho server học tập Build Phase

> Phiên bản: 2.0  
> Trạng thái: Đề xuất triển khai  
> Phạm vi đầu tiên: MVP trong khoảng 1,5 ngày  

---

## 0. Tóm tắt

Xây dựng một Discord bot làm trợ lý AI cho cộng đồng học tập **Build Phase**. Bot có ba nhóm nhiệm vụ:

1. Trả lời câu hỏi của học viên dựa trên dữ liệu và nguồn chính thức của chương trình.
2. Giúp học viên nắm lại các cuộc trò chuyện đã bỏ lỡ bằng bản tóm tắt có cấu trúc.
3. Làm nổi bật thông báo quan trọng từ admin/BTC/mentor, đặc biệt là deadline, lịch học, thay đổi quy định và việc học viên cần thực hiện.

Nếu không có đủ bằng chứng để trả lời, bot phải nói rõ rằng mình chưa chắc chắn, tag đúng người phụ trách và ghi câu hỏi vào channel hỗ trợ. Bot không được suy đoán hoặc tạo ra thông tin không có trong nguồn.

### Mô tả sản phẩm ngắn

> Trợ lý AI cho cộng đồng học tập Build Phase, giúp học viên hỏi đáp dựa trên nguồn chính thức, nhanh chóng nắm lại những cuộc trò chuyện đã bỏ lỡ, theo dõi thông báo quan trọng từ admin và chuyển câu hỏi chưa chắc chắn đến đúng người phụ trách.

---

## 1. Nguyên tắc sản phẩm

1. **Có nguồn:** Câu trả lời, deadline và thông báo quan trọng phải dẫn về tin nhắn hoặc tài liệu gốc.
2. **Không đoán:** Không đủ dữ liệu thì chuyển cho con người thay vì trả lời bừa.
3. **Ưu tiên thông tin chính thức:** Tin nhắn của admin/BTC/mentor và channel thông báo có độ ưu tiên cao hơn thảo luận thông thường.
4. **Đúng phạm vi:** Bot tập trung vào chương trình Build Phase.
5. **Không làm lộ dữ liệu:** Người dùng chỉ nhận nội dung từ những channel mà họ có quyền xem.
6. **Không gây spam:** Bot chỉ phản hồi trong channel được cấu hình, khi được mention hoặc khi người dùng gọi lệnh.
7. **Con người quyết định cuối cùng:** Với nội dung có độ tin cậy thấp hoặc nhạy cảm, mentor/admin là người xác nhận.

---

## 2. Mục tiêu và phạm vi

### 2.1 Mục tiêu MVP

MVP phải chứng minh được ba chức năng cốt lõi:

1. Bot trả lời đúng câu hỏi lặp lại về Build Phase và trích dẫn nguồn.
2. Bot biết khi nào không nên tự trả lời, sau đó route đúng mentor/admin.
3. Mentor/BTC có một channel để theo dõi câu hỏi chưa được xử lý.

### 2.2 Mục tiêu giai đoạn tiếp theo

Sau khi luồng cốt lõi hoạt động ổn định:

1. Học viên dùng `/catchup` để tóm tắt nội dung mới.
2. Học viên dùng `/important` để xem thông báo quan trọng từ admin.
3. Bot lưu mốc tổng hợp riêng cho từng người dùng.
4. Người dùng có thể phản hồi câu trả lời bằng 👍, 👎 hoặc yêu cầu mentor.

### 2.3 Phạm vi kiến thức

Bot hỗ trợ các nội dung thuộc Build Phase, bao gồm:

- Lịch học, workshop và mentoring.
- Deadline nộp bài hoặc project.
- Yêu cầu, rubric và quy định nộp bài.
- Tài liệu học tập và đường dẫn chính thức.
- Quy định hoạt động của chương trình.
- Thông báo và thay đổi từ admin/BTC.
- Hướng dẫn sử dụng các công cụ được dùng trong chương trình.
- Các câu hỏi kỹ thuật có liên quan trực tiếp đến bài học và project.

### 2.4 Ngoài phạm vi MVP

- Không xử lý toàn bộ lịch sử chat cũ nếu bot không có quyền hoặc dữ liệu chưa được xuất.
- Không xây dashboard web riêng; sử dụng Discord channel làm dashboard.
- Không dùng ML để matching mentor; dùng mapping thủ công bằng JSON/YAML.
- Không cam kết biết chính xác người dùng đã đọc tin nhắn nào.
- Không tự động trả lời các vấn đề nhạy cảm hoặc không có nguồn.
- Không xây hệ thống reminder/escalation phức tạp trong MVP.
- Không làm thêm tính năng trước khi Story P0 hoạt động end-to-end.

---

## 3. User stories và mức ưu tiên

| # | Priority | User story |
|---|---|---|
| 1 | P0 | Là học viên, tôi hỏi một câu về Build Phase và nhận câu trả lời kèm nguồn nếu hệ thống tìm thấy thông tin phù hợp. |
| 2 | P0 | Là học viên, nếu bot không đủ chắc chắn, bot nói rõ điều đó và tag đúng mentor/admin phụ trách. |
| 3 | P0 | Là mentor/BTC, tôi thấy các câu hỏi chưa được giải quyết trong channel `#cần-hỗ-trợ`. |
| 4 | P1 | Là học viên, tôi gọi `/catchup` để xem bản tóm tắt nội dung mới trong một khoảng thời gian. |
| 5 | P1 | Là học viên, tôi gọi `/important` để xem các thông báo quan trọng từ admin/BTC/mentor. |
| 6 | P1 | Là học viên, tôi có thể mở nguồn gốc của từng ý trong câu trả lời hoặc bản tóm tắt. |
| 7 | P1 | Là người dùng, tôi có thể đánh dấu nội dung đến thời điểm hiện tại là đã được bot tổng hợp. |
| 8 | P1 | Là người dùng, tôi có thể báo câu trả lời không đúng hoặc yêu cầu mentor hỗ trợ. |
| 9 | P2 | Là học viên mới, tôi được gợi ý 1–2 tài liệu hoặc channel bắt đầu phù hợp. |
| 10 | P2 | Là mentor, tôi nhận digest cuối ngày về các câu hỏi hot và tồn đọng. |
| 11 | P2 | Là mentor, tôi nhận bản nháp do AI soạn và duyệt trước khi gửi cho học viên. |
| 12 | P3 | Là BTC, tôi xem được số liệu về câu hỏi phổ biến, thời gian phản hồi và tỷ lệ câu trả lời hữu ích. |

### Chốt cho MVP 1,5 ngày

- Bắt buộc: Story 1, 2 và 3.
- Nếu core đã ổn định: triển khai Story 4, 5 và 6 theo thứ tự.
- Các Story còn lại đưa vào backlog.

---

## 4. Kiến trúc tổng quan

```text
┌──────────────────────────────┐
│ Discord Server               │
│ FAQ / hỏi-đáp / thông báo    │
└──────────────┬───────────────┘
               │ message events / slash commands
               ▼
┌──────────────────────────────┐
│ Discord Bot                  │
│ listener + command router    │
└───────┬──────────┬───────────┘
        │          │
        │          ├──────────────────────────────┐
        ▼          ▼                              ▼
┌────────────┐ ┌──────────────┐          ┌────────────────┐
│ Ingest     │ │ Q&A Handler  │          │ Summary Handler│
│ Pipeline   │ │ /ask         │          │ /catchup       │
└─────┬──────┘ └──────┬───────┘          │ /important     │
      │               │                  └───────┬────────┘
      ▼               ▼                          │
┌──────────────────────────────┐                 │
│ Vector DB + Metadata Store   │◄────────────────┘
│ text, author, role, link,     │
│ channel, timestamp, embedding│
└──────────────┬───────────────┘
               │ retrieve/filter
               ▼
┌──────────────────────────────┐
│ LLM                          │
│ answer / summary / confidence│
│ structured JSON output       │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
Confidence cao     Confidence thấp
Trả lời + nguồn    Báo chưa chắc
                   + tag mentor
                   + log hỗ trợ
```

### Thành phần lưu trữ

1. **Vector DB:** lưu embedding để tìm nội dung liên quan.
2. **Metadata store:** lưu nội dung gốc, tác giả, role, thời gian, channel và link.
3. **User checkpoint store:** lưu lần cuối người dùng xác nhận đã tổng hợp nội dung.
4. **Routing config:** ánh xạ chủ đề với mentor/role.

Với MVP có thể dùng SQLite cho metadata/checkpoint và Chroma cho vector.

---

## 5. Nguồn dữ liệu và mức độ ưu tiên

### 5.1 Nguồn dữ liệu được phép

- Tin nhắn mới trong các channel được cấu hình.
- Tin nhắn được ghim.
- Channel thông báo chính thức.
- FAQ, handbook, rubric hoặc tài liệu tĩnh do BTC cung cấp.
- Tài liệu được admin đánh dấu là nguồn chính thức.

### 5.2 Không dùng làm nguồn

- Tin nhắn từ channel nằm ngoài danh sách cho phép.
- Nội dung người dùng hiện tại không có quyền xem.
- Tin nhắn đã bị xóa.
- Tin nhắn của bot khác, trừ khi được cấu hình rõ ràng.
- Đoạn chat đùa, emoji-only hoặc quá ngắn và không có giá trị kiến thức.

### 5.3 Thứ tự ưu tiên nguồn

1. Tin nhắn mới nhất từ admin/BTC trong channel thông báo.
2. Tài liệu chính thức và tin nhắn được ghim.
3. Tin nhắn từ mentor phụ trách.
4. FAQ đã được xác nhận.
5. Thảo luận cộng đồng.

Khi nguồn mâu thuẫn, bot không tự kết luận. Bot phải hiển thị cảnh báo, dẫn cả hai nguồn và tag admin/mentor nếu cần.

---

## 6. Luồng xử lý chi tiết

### 6.1 Ingest dữ liệu

Bot chỉ theo dõi các channel được cấu hình. Với mỗi tin nhắn mới hợp lệ:

1. Kiểm tra bot có được phép ingest channel hay không.
2. Bỏ qua emoji-only, tin quá ngắn, tin của chính bot và nội dung không cần thiết.
3. Lưu:
   - `message_id`
   - Nội dung
   - Tác giả
   - Role của tác giả
   - Thời gian
   - Channel
   - Link tin nhắn
   - Trạng thái pinned/important
4. Tạo embedding.
5. Lưu embedding vào Vector DB.

Nếu có tài liệu tĩnh, chạy seed một lần khi setup để bot có dữ liệu ngay.

### 6.2 Hỏi đáp Build Phase

Người dùng có thể hỏi bằng một trong các cách:

- Gửi câu hỏi trong channel hỏi đáp.
- Mention bot.
- Dùng `/ask <câu hỏi>`.

Luồng:

1. Kiểm tra câu hỏi có thuộc phạm vi Build Phase hay không.
2. Tìm top-k nội dung liên quan trong Vector DB.
3. Áp dụng ngưỡng similarity tối thiểu.
4. Gọi LLM với câu hỏi, context và yêu cầu trả JSON.
5. Kiểm tra nguồn do LLM trả về có thật trong context.
6. Trả lời hoặc route cho mentor.

Schema đề xuất:

```json
{
  "answer": "Nội dung trả lời",
  "confidence": "high",
  "sources": [
    {
      "message_id": "123456789",
      "label": "Thông báo deadline"
    }
  ],
  "topic": "deadline",
  "needs_human": false
}
```

#### Confidence cao

Bot trả:

```text
Deadline nộp Project 1 là 23:59 ngày 15/08.

Nguồn:
- Thông báo của BTC: [Xem tin nhắn]
```

#### Confidence thấp

Bot trả:

```text
Mình chưa tìm thấy thông tin đủ chắc chắn để trả lời câu này.
Mình đã tag @mentor-devops và ghi câu hỏi vào #cần-hỗ-trợ.
```

Đồng thời bot gửi log vào `#cần-hỗ-trợ`.

### 6.3 Routing mentor/admin

Dùng file JSON hoặc YAML:

```json
{
  "deploy,docker,server,render": "DISCORD_ROLE_MENTOR_DEVOPS",
  "model,training,fine-tune,cuda": "DISCORD_ROLE_MENTOR_ML",
  "điểm,chấm bài,rubric,deadline": "DISCORD_ROLE_TA_ACADEMIC",
  "lịch học,sự kiện,quy định": "DISCORD_ROLE_BTC"
}
```

Cách match MVP:

1. Chuẩn hóa chữ thường và dấu câu.
2. Kiểm tra keyword trong câu hỏi và topic do LLM phân loại.
3. Chọn role có nhiều keyword match nhất.
4. Nếu không match, dùng role mặc định `@mentor-oncall`.

### 6.4 Channel hỗ trợ mentor

Mỗi câu hỏi confidence thấp được đăng dưới dạng:

```text
❓ Câu hỏi cần hỗ trợ
Người hỏi: @hoc-vien
Channel: #build-phase
Nội dung: "Làm sao khắc phục lỗi CUDA out of memory?"
Đã route: @mentor-ml
Nguồn gần nhất: Không có nguồn đủ mạnh
Tin nhắn gốc: [Mở tin nhắn]
Trạng thái: ⏳ Chưa xử lý
```

Quy ước trạng thái:

- ⏳ Chưa xử lý
- 👀 Đang xem
- ✅ Đã xử lý

Trong MVP, mentor dùng reaction để cập nhật trạng thái.

### 6.5 Tóm tắt hội thoại bằng `/catchup`

Các lệnh dự kiến:

```text
/catchup
/catchup period:24h
/catchup period:7d
/catchup channel:#build-phase
```

Nếu người dùng không chỉ định khoảng thời gian:

- Lấy dữ liệu từ `last_catchup_at` của người đó.
- Nếu chưa có checkpoint, mặc định lấy 24 giờ gần nhất.
- Giới hạn tối đa số ngày và số tin nhắn để tránh prompt quá lớn.

Bot nhóm nội dung theo chủ đề và trả theo cấu trúc:

```text
📌 TÓM TẮT NỘI DUNG MỚI
Khoảng thời gian: 09:00 30/07 → 18:00 30/07

🚨 Khẩn cấp
- Deadline Project 1 được chuyển sang 23:59 ngày 15/08.
  Nguồn: [Xem thông báo]

📢 Thông báo từ admin
- Workshop tối nay chuyển sang Google Meet.
  Nguồn: [Xem thông báo]

✅ Việc bạn cần làm
- Điền form đăng ký mentor trước 12/08.
  Nguồn: [Mở form/thông báo]

💬 Chủ đề thảo luận nổi bật
- Nhiều học viên gặp lỗi khi deploy lên Render.
  Nguồn: [Xem thread]

📚 Tài liệu được chia sẻ
- Hướng dẫn deploy Project 1.
  Nguồn: [Mở tài liệu]

❓ Câu hỏi chưa có lời giải
- Cách cấu hình biến môi trường trên Render.
  Nguồn: [Xem câu hỏi]
```

Quy tắc tóm tắt:

- Không viết thành một đoạn văn dài.
- Gộp các tin nhắn trùng hoặc cùng chủ đề.
- Ưu tiên admin, deadline, quyết định và action item.
- Không bỏ qua thông báo admin chỉ vì ít reaction.
- Mỗi ý quan trọng phải có nguồn.
- Không đưa nội dung từ channel người dùng không có quyền xem.

### 6.6 Thông báo quan trọng bằng `/important`

Các lệnh:

```text
/important
/important period:7d
/important channel:#announcements
```

Một tin nhắn được xem là quan trọng nếu thỏa một hoặc nhiều điều kiện:

1. Được gửi bởi người có role admin/BTC/mentor được cấu hình.
2. Nằm trong channel thông báo.
3. Là tin nhắn được ghim.
4. Có reaction quy ước 📌 hoặc 🚨 từ admin.
5. Có nội dung về deadline, lịch học, bắt buộc, thay đổi hoặc hủy sự kiện.

Điểm ưu tiên đề xuất:

| Điều kiện | Điểm |
|---|---:|
| Admin/BTC gửi | +4 |
| Channel thông báo | +3 |
| Tin nhắn được ghim | +3 |
| Admin đánh dấu 📌/🚨 | +4 |
| Có deadline/ngày giờ | +2 |
| Có từ khóa bắt buộc/thay đổi/hủy | +2 |
| Chỉ là thảo luận thông thường | +0 |

Thông báo có tổng điểm từ ngưỡng cấu hình trở lên sẽ xuất hiện trong `/important`.

### 6.7 Giới hạn về trạng thái “đã đọc”

Discord không cung cấp cho bot trạng thái read receipt chính xác của từng người dùng. Vì vậy:

- Bot không được nói: “Đây là tất cả tin nhắn bạn chưa đọc”.
- Bot nên nói: “Đây là nội dung mới kể từ lần bạn tổng hợp gần nhất”.
- `last_catchup_at` là mốc của bot, không phải trạng thái đã đọc chính thức của Discord.

Schema checkpoint:

```json
{
  "discord_user_id": "123456789",
  "guild_id": "987654321",
  "last_catchup_at": "2026-07-30T10:00:00Z"
}
```

Sau bản tóm tắt, bot hiển thị:

```text
Bạn có muốn đánh dấu nội dung đến thời điểm này là đã được tổng hợp không?
[✅ Đánh dấu] [❌ Chưa]
```

Chỉ cập nhật checkpoint khi người dùng chọn **Đánh dấu**.

### 6.8 Phản hồi chất lượng

Sau câu trả lời, bot cho phép người dùng chọn:

```text
Câu trả lời này có hữu ích không?
[👍 Có] [👎 Không đúng] [🙋 Cần mentor]
```

Nếu chọn `👎 Không đúng` hoặc `🙋 Cần mentor`:

1. Ghi sự kiện feedback.
2. Đẩy câu hỏi vào `#cần-hỗ-trợ`.
3. Tag mentor thích hợp.
4. Không dùng câu trả lời chưa được xác minh làm nguồn kiến thức.

### 6.9 Mentor Research Tool — stretch

Khi confidence thấp, bot có thể tạo bản nháp riêng cho mentor:

```text
🔍 Bản nháp trả lời cho câu hỏi của @học-viên
Câu hỏi: "..."

Bản nháp AI:
[Nội dung và nguồn tham khảo]

[✅ Gửi nguyên văn] [✏️ Sửa rồi gửi] [❌ Bỏ qua]
```

AI không tự gửi bản nháp này cho học viên. Mentor luôn là người duyệt cuối cùng.

Chỉ triển khai khi Story 1–3 đã chạy ổn định và được test end-to-end.

---

## 7. Quy tắc an toàn và chống hallucination

1. Chỉ trả lời dựa trên context được retrieve.
2. Không tạo URL hoặc message ID không tồn tại.
3. Kiểm tra tất cả source ID trước khi gửi.
4. Nếu similarity thấp hơn ngưỡng, tự động route mà không cần LLM quyết định.
5. Không suy diễn deadline, điểm số hoặc quy định.
6. Nếu có hai nguồn mâu thuẫn:
   - Hiển thị cảnh báo.
   - Dẫn cả hai nguồn.
   - Ưu tiên nguồn mới hơn nhưng không tự khẳng định nguồn cũ mất hiệu lực.
   - Tag admin/BTC để xác nhận.
7. Không trả lời thay admin về nội dung nhạy cảm, khiếu nại hoặc quyết định cá nhân.
8. Không lưu token, secret hoặc thông tin riêng tư trong log.

---

## 8. Cấu hình đề xuất

### 8.1 File `.env`

```env
# Discord
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
DISCORD_QA_CHANNEL_IDS=
DISCORD_ANNOUNCEMENT_CHANNEL_IDS=
DISCORD_SUPPORT_CHANNEL_ID=

# Role IDs
DISCORD_ADMIN_ROLE_IDS=
DISCORD_MENTOR_ROLE_IDS=
DISCORD_DEFAULT_SUPPORT_ROLE_ID=

# AI
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=

# Retrieval
VECTOR_DB_PATH=./data/chroma
TOP_K=5
SIMILARITY_THRESHOLD=0.72

# Summary
DEFAULT_CATCHUP_HOURS=24
MAX_CATCHUP_DAYS=7
IMPORTANT_SCORE_THRESHOLD=4

# Application
DATABASE_PATH=./data/bot.sqlite3
LOG_LEVEL=INFO
```

Không commit file `.env` lên Git. Tạo `.env.example` chỉ chứa tên biến và giá trị mẫu.

### 8.2 File routing

Ví dụ `routing.json`:

```json
{
  "routes": [
    {
      "keywords": ["deploy", "docker", "server", "render"],
      "role_id": "MENTOR_DEVOPS_ROLE_ID"
    },
    {
      "keywords": ["model", "training", "fine-tune", "cuda"],
      "role_id": "MENTOR_ML_ROLE_ID"
    },
    {
      "keywords": ["điểm", "chấm bài", "rubric", "deadline"],
      "role_id": "TA_ACADEMIC_ROLE_ID"
    }
  ],
  "default_role_id": "MENTOR_ONCALL_ROLE_ID"
}
```

---

## 9. Lệnh Discord đề xuất

| Lệnh | Priority | Mô tả |
|---|---|---|
| `/ask` | P0 | Hỏi bot về Build Phase. |
| `/catchup` | P1 | Tóm tắt nội dung mới theo thời gian hoặc channel. |
| `/important` | P1 | Xem thông báo quan trọng từ admin/BTC/mentor. |
| `/resources` | P2 | Xem tài liệu chính thức theo chủ đề. |
| `/help` | P0 | Xem cách sử dụng bot. |
| `/admin-mark-important` | P2 | Admin đánh dấu một nội dung quan trọng. |
| `/admin-reindex` | P2 | Nạp lại dữ liệu được cho phép. |
| `/admin-test-route` | P2 | Kiểm tra routing mentor. |

Trong MVP, có thể thay `/admin-mark-important` bằng reaction 📌 để giảm thời gian phát triển.

---

## 10. Tech stack đề xuất

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Bot framework | `discord.py` hoặc `discord.js` | Chọn ngôn ngữ team thành thạo nhất. |
| LLM | Claude API, model Sonnet phù hợp | Hỗ trợ output có cấu trúc. |
| Vector DB | Chroma local | Nhanh, không cần dựng server riêng. |
| Metadata/checkpoint | SQLite | Đủ cho MVP và dễ backup. |
| Embedding | API embedding hoặc sentence-transformers | Không tự train model. |
| Routing | JSON/YAML | Dễ chỉnh trước demo. |
| Hosting | Máy cá nhân, VPS hoặc dịch vụ free tier | Chỉ cần ổn định trong demo. |

---

## 11. Quyền và setup Discord

1. Tạo Discord Application và Bot trên Discord Developer Portal.
2. Bật **Message Content Intent**.
3. Tạo link invite với scope:
   - `bot`
   - `applications.commands`
4. Quyền tối thiểu:
   - View Channel
   - Send Messages
   - Read Message History
   - Add Reactions
   - Embed Links
   - Use Application Commands
5. Không cấp Administrator nếu không thực sự cần.
6. Gửi link invite cho admin/mod sớm vì đây là phụ thuộc bên ngoài.
7. Tạo server test riêng trong lúc chờ duyệt.
8. Bật Developer Mode trên Discord để lấy Guild ID, Channel ID, Role ID và User ID.

---

## 12. Phân quyền và riêng tư

1. Chỉ ingest channel nằm trong allowlist.
2. Trước khi hiển thị source, kiểm tra người gọi có quyền xem channel nguồn.
3. Không đưa nội dung private mentor/admin vào bản tóm tắt cho học viên.
4. Không log toàn bộ nội dung nhạy cảm ở mức `INFO`.
5. Cho phép admin tắt ingest đối với một channel.
6. Có cơ chế xóa hoặc reindex dữ liệu nếu một tin nhắn nguồn bị xóa/sửa.
7. Nêu rõ với thành viên server rằng bot đang xử lý tin nhắn trong các channel được chỉ định.

---

## 13. Timeline đề xuất

### Giai đoạn A — MVP core, khoảng 12 giờ

| Thời gian | Công việc |
|---|---|
| Giờ 1 | Setup Discord app/bot, server test, quyền và cấu hình ID. |
| Giờ 2–4 | Listener, ingest, metadata và Vector DB. |
| Giờ 2–4 | Prompt Q&A, JSON schema, confidence và source validation. |
| Giờ 4–6 | Ghép retrieve → LLM → reply có nguồn. |
| Giờ 5–7 | Routing mentor và channel `#cần-hỗ-trợ`. |
| Giờ 7–9 | Test Story 1–3 end-to-end, seed dữ liệu thật. |
| Giờ 9–10 | Test trên server thật nếu được duyệt. |
| Giờ 10–11 | Sửa lỗi, polish format và chuẩn bị câu hỏi demo. |
| Giờ 11–12 | Slide, checklist và video demo dự phòng. |

### Giai đoạn B — Catch-up và admin intelligence

Thực hiện sau khi MVP core ổn định:

1. Lưu role/channel metadata.
2. Làm `/important` bằng rule-based scoring.
3. Làm `/catchup` theo khoảng thời gian.
4. Thêm source validation cho từng ý tóm tắt.
5. Thêm checkpoint `last_catchup_at`.
6. Thêm feedback buttons.

Không cố nhồi toàn bộ Giai đoạn B vào 1,5 ngày nếu Story 1–3 chưa ổn.

---

## 14. Kịch bản demo

### Demo 1 — Câu hỏi có trong dữ liệu

Học viên hỏi:

```text
Deadline nộp Project 1 là khi nào?
```

Kỳ vọng:

- Bot trả lời đúng.
- Có link thông báo gốc.
- Không tag mentor.

### Demo 2 — Câu hỏi ngoài dữ liệu

Học viên hỏi:

```text
Làm sao sửa lỗi CUDA out of memory trong bài của mình?
```

Kỳ vọng:

- Bot nói chưa có thông tin đủ chắc chắn.
- Tag đúng mentor ML/DevOps.
- Đăng log vào `#cần-hỗ-trợ`.

### Demo 3 — Dashboard mentor

- Mở `#cần-hỗ-trợ`.
- Thấy câu hỏi từ Demo 2.
- Mentor react 👀 rồi ✅.

### Demo 4 — Tóm tắt nội dung

Người dùng gọi:

```text
/catchup period:24h
```

Kỳ vọng:

- Có thông báo admin.
- Có deadline/action item.
- Có chủ đề nổi bật.
- Mỗi ý quan trọng có source.
- Không hiển thị channel người dùng không được phép xem.

### Demo 5 — Thông báo quan trọng

Người dùng gọi:

```text
/important period:7d
```

Kỳ vọng:

- Thông báo của admin được ưu tiên.
- Tin pinned/📌 xuất hiện.
- Sắp xếp theo độ quan trọng và thời gian.

---

## 15. Test cases bắt buộc

### Q&A

- Câu hỏi có nguồn rõ ràng → trả lời kèm source.
- Không có nguồn đủ gần → route mentor.
- LLM tạo source ID sai → không gửi source giả.
- Hai nguồn mâu thuẫn → cảnh báo và tag admin.
- Câu hỏi ngoài Build Phase → từ chối nhẹ nhàng hoặc route mặc định.

### Catch-up

- Người dùng chưa có checkpoint → lấy 24 giờ gần nhất.
- Có checkpoint → lấy từ checkpoint.
- Người dùng không xác nhận đánh dấu → không cập nhật checkpoint.
- Có 100+ tin nhắn → chunk, gom nhóm và giới hạn prompt.
- Channel private → không xuất hiện trong tóm tắt.
- Thông báo admin ít reaction → vẫn xuất hiện.

### Important

- Tin admin + deadline → điểm cao.
- Tin trong announcement channel → được ưu tiên.
- Tin thường không có tín hiệu → không xuất hiện.
- Admin đánh dấu 📌/🚨 → xuất hiện.
- Thông báo cũ và mới mâu thuẫn → hiển thị cảnh báo.

### Routing

- Keyword rõ ràng → tag đúng role.
- Nhiều route cùng match → chọn route có điểm cao nhất.
- Không match → tag role mặc định.

---

## 16. Rủi ro và phương án dự phòng

| Rủi ro | Phương án |
|---|---|
| Admin chưa duyệt invite bot | Demo trên server test với dữ liệu seed giống thật. |
| Confidence của LLM không ổn định | Dùng similarity threshold cứng trước khi gọi LLM. |
| Bot tạo nguồn không tồn tại | Validate message/document ID ở backend. |
| Tóm tắt bỏ sót thông báo admin | Áp dụng rule ưu tiên role và channel trước bước LLM. |
| Prompt quá dài | Chunk theo thời gian/chủ đề, map-reduce summary và giới hạn số ngày. |
| Bot không biết trạng thái đã đọc thật | Dùng checkpoint của `/catchup` và mô tả rõ giới hạn. |
| Bot lộ nội dung private | Kiểm tra quyền Discord của người gọi trước khi retrieve/hiển thị. |
| Bot crash lúc demo | Chuẩn bị video backup và health check đơn giản. |
| Dữ liệu thật quá ít | Seed FAQ, handbook, rubric và thông báo mẫu. |
| Thông báo mâu thuẫn | Dẫn cả hai nguồn và tag admin xác nhận. |

---

## 17. Backlog

Chỉ làm sau khi Story P0 ổn định:

1. `/important` và rule scoring.
2. `/catchup` theo thời gian/channel.
3. Checkpoint riêng cho từng người.
4. Feedback 👍/👎/🙋.
5. Mentor Research Tool.
6. Onboarding cho học viên mới.
7. Digest cuối ngày.
8. Reminder deadline theo lựa chọn của người dùng.
9. Escalation nếu câu hỏi chưa được xử lý sau X giờ.
10. Tìm kiếm tài liệu bằng `/resources`.
11. Metrics về thời gian phản hồi và chất lượng.
12. Admin console hoặc dashboard web nếu quy mô tăng.

---

## 18. Định nghĩa “Done”

### MVP core hoàn thành khi

- Bot chạy ổn định trên server test hoặc server thật.
- Trả lời đúng ít nhất 3 câu hỏi mẫu có nguồn.
- Route đúng ít nhất 2 câu hỏi ngoài dữ liệu.
- Câu hỏi confidence thấp xuất hiện trong `#cần-hỗ-trợ`.
- Source link mở đúng tin nhắn/tài liệu.
- Không cần giải thích thủ công để hoàn thành kịch bản demo.

### Catch-up hoàn thành khi

- `/catchup` tạo bản tóm tắt có cấu trúc.
- Thông báo admin, deadline và action item được ưu tiên.
- Mỗi ý quan trọng có source hợp lệ.
- Không lộ channel người dùng không được phép xem.
- Checkpoint chỉ cập nhật sau khi người dùng xác nhận.

### Important hoàn thành khi

- `/important` tìm đúng các thông báo admin/pinned/được đánh dấu.
- Thông báo được sắp xếp hợp lý.
- Deadline và thay đổi quan trọng có source.
- Các nguồn mâu thuẫn được cảnh báo thay vì tự kết luận.

---

## 19. Chỉ số theo dõi sau MVP

- Tỷ lệ câu hỏi được bot trả lời có ích.
- Tỷ lệ câu trả lời bị bấm 👎.
- Tỷ lệ câu hỏi phải chuyển mentor.
- Thời gian trung bình để mentor xử lý.
- Số thông báo quan trọng được người học mở nguồn.
- Số người sử dụng `/catchup` hàng tuần.
- Chủ đề được hỏi nhiều nhất.
- Các câu hỏi chưa có tài liệu chính thức.

Những chỉ số này dùng để quyết định cần bổ sung FAQ, tài liệu hay mentor routing ở đâu; không dùng để đánh giá cá nhân học viên.

