# Build Phase Discord Assistant

Bot Python dùng `discord.py`, triển khai P0 của
`spec-build-phase-discord-bot-v2.md`: hỏi đáp có nguồn, ingest có allowlist và
chuyển câu hỏi chưa chắc chắn cho mentor/admin.

## Chức năng

- `/ask question:...`: tra cứu nguồn được phép, gọi Claude và chỉ trả lời khi
  confidence cao cùng source ID hợp lệ.
- Hỏi trực tiếp bằng câu kết thúc bằng `?` hoặc mention bot trong kênh Q&A.
- `/help`: xem cách dùng và trạng thái cấu hình, không hiển thị secret.
- `/admin-reindex [channel]`: nạp lại tối đa số tin đã cấu hình.
- `/admin-test-route question:...`: kiểm tra keyword routing và role đích.
- Ingest tin mới, cập nhật khi tin bị sửa và xóa khỏi SQLite khi tin gốc bị xóa.
- Kiểm tra lại quyền xem kênh và fetch tin gốc ngay trước khi hiển thị nguồn.
- Phát hiện deadline/ngày giờ mâu thuẫn và chuyển cho admin.
- Câu hỏi thiếu nguồn, confidence thấp hoặc lỗi AI được ghi vào kênh hỗ trợ.
- Mentor/admin dùng reaction `👀` và `✅` để cập nhật trạng thái support case.
- Chặn credential có dạng API key/token/password trước khi lưu hoặc chuyển tiếp.
- Các lệnh starter vẫn còn: `/ping`, `/hello`, `/userinfo`, `/note` và `/clear`.

Bot không tự đoán thông tin và không tự ingest dữ liệu mẫu trong repository.

## 1. Cài đặt

Yêu cầu Python 3.11 trở lên. Trong thư mục `discord-bot`:

```powershell
.\setup.ps1
```

Script tạo `.venv` và cài dependency trong `requirements-dev.txt`.

## 2. Cấu hình Discord

Trong Discord Developer Portal:

1. Mở application, chọn **Bot**.
2. Bật **Message Content Intent**.
3. Invite bot với scope `bot` và `applications.commands`.
4. Chỉ cấp các quyền cần thiết:
   - View Channel
   - Send Messages
   - Read Message History
   - Add Reactions
   - Embed Links
   - Use Application Commands

Không cần cấp Administrator. Nếu vẫn dùng `/clear`, bot cần thêm Manage Messages
tại kênh tương ứng.

## 3. Điền `.env`

Copy `.env.example` thành `.env` nếu file chưa tồn tại. Các giá trị P0:

```env
DISCORD_TOKEN=token_bot
DISCORD_GUILD_ID=id_server_test

DISCORD_QA_CHANNEL_IDS=id_qa_1,id_qa_2
DISCORD_ANNOUNCEMENT_CHANNEL_IDS=id_thong_bao
DISCORD_SUPPORT_CHANNEL_ID=id_kenh_can_ho_tro

DISCORD_ADMIN_ROLE_IDS=id_role_admin
DISCORD_MENTOR_ROLE_IDS=id_role_mentor_1,id_role_mentor_2
DISCORD_DEFAULT_SUPPORT_ROLE_ID=id_role_mentor_oncall

ENABLE_MESSAGE_CONTENT_INTENT=true
ANTHROPIC_API_KEY=key_anthropic
ANTHROPIC_MODEL=claude-sonnet-5
```

Lấy ID bằng cách bật Developer Mode trong Discord rồi dùng **Copy ID**. Nhiều ID
được ngăn bằng dấu phẩy.

Không gửi token hoặc API key qua Discord, chat hay commit Git. Nếu credential từng
bị lộ, hãy rotate/reset trước khi tiếp tục.

### Routing theo chủ đề

Mở `config/routing.json` và thay các chuỗi ví dụ như
`MENTOR_DEVOPS_ROLE_ID` bằng Role ID thật:

```json
{
  "name": "devops",
  "keywords": ["deploy", "docker", "server", "render"],
  "role_id": 123456789012345678,
  "priority": 20
}
```

Role ID trong file chỉ được bot sử dụng nếu role đó cũng nằm trong
`DISCORD_ADMIN_ROLE_IDS`, `DISCORD_MENTOR_ROLE_IDS` hoặc là
`DISCORD_DEFAULT_SUPPORT_ROLE_ID`. Quy tắc này ngăn cấu hình routing tag nhầm
role không được ủy quyền.

Role mentor/admin cần bật **Allow anyone to @mention this role**, hoặc bot cần
quyền **Mention @everyone, @here, and All Roles** trong kênh hỗ trợ. Nếu không,
support case vẫn được ghi nhưng Discord sẽ không gửi thông báo mention.

## 4. Chạy bot

```powershell
.\run.ps1
```

Khi log có `Bot đã online`, chạy lần lượt:

1. `/help` để kiểm tra trạng thái.
2. `/admin-test-route` để xác minh role đích.
3. `/admin-reindex` để nạp tin thật từ các kênh allowlist.
4. `/ask` với một câu có nguồn chính thức.
5. `/ask` với một câu chưa có nguồn và kiểm tra kênh support.

Dừng tiến trình nền:

```powershell
.\stop.ps1
```

## 5. Quy tắc dữ liệu và riêng tư

- Chỉ tin trong `DISCORD_QA_CHANNEL_IDS` và
  `DISCORD_ANNOUNCEMENT_CHANNEL_IDS` mới được ingest.
- `/ask`, mention và câu hỏi tự động chỉ hoạt động trong kênh Q&A allowlist.
- Tin bot/webhook, tin quá ngắn, emoji-only, câu hỏi và credential không được
  dùng làm knowledge source.
- Người gọi chỉ nhận nguồn từ kênh họ có cả View Channel và Read Message History.
- P0 không ingest hoặc trích dẫn private thread; Discord không cho phép kiểm tra
  membership private thread an toàn chỉ bằng quyền kế thừa từ parent.
- Câu trả lời slash command mặc định là ephemeral (`ASK_EPHEMERAL=true`).
- Community source quá thời hạn bị xóa theo `SOURCE_RETENTION_DAYS`; nguồn official
  không bị cleanup tự động.
- Support case đã ở trạng thái `resolved` bị xóa theo
  `SUPPORT_CASE_RETENTION_DAYS` (mặc định 90 ngày); case đang chờ không tự mất.
- Public thread chỉ hoạt động khi chính Thread ID nằm trong allowlist; cấu hình
  Parent Channel ID không tự mở rộng sang các thread con.
- SQLite nằm ở `data/bot.db`. Không commit file database hoặc `.env`.

### Vì sao P0 dùng lexical retrieval

Anthropic không cung cấp embedding model riêng trong Claude API. P0 dùng tìm kiếm
từ khóa tiếng Việt không phân biệt dấu trong SQLite để bot chạy với đúng một nhà
cung cấp AI. Vector/semantic retrieval chỉ nên thêm khi team chốt embedding
provider, chi phí và chính sách dữ liệu.

## 6. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Test phủ config, SQLite, ingest, retrieval, conflict detection, routing, output
Claude có cấu trúc, source validation và credential guard.

## 7. Cấu trúc chính

```text
discord-bot/
├── app/
│   ├── cogs/assistant.py   # Discord commands/listeners và support workflow
│   ├── ai.py               # Claude strict tool output
│   ├── qa.py               # Quyết định answer/escalate/conflict
│   ├── retrieval.py        # Lexical retrieval và conflict detection
│   ├── ingest.py           # Allowlist ingest
│   ├── routing.py          # Keyword routing
│   ├── safety.py           # Credential guard
│   ├── database.py         # SQLite
│   └── config.py
├── config/routing.json
├── tests/
├── .env.example
├── main.py
└── requirements.txt
```

Story P1 (`/catchup`, `/important`) được giữ lại cho phase tiếp theo sau khi P0
chạy end-to-end bằng dữ liệu thật trên server.
