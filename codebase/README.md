# Trợ lý Học viên Discord — MVP (Hướng B)

Lát cắt: **Học viên hỏi logistics/FAQ trên Discord → bot chỉ trả lời khi có căn cứ trong knowledge → nếu không chắc thì tag Mentor.**

## Đã có trong MVP

| Lớp | Tính năng | Trạng thái |
|---|---|---|
| 1 · RAG | Index `knowledge/*.md` + sync kênh Discord (JSON + TF cosine, không Chroma) | Working |
| 1 · RAG | `/ask` và `@bot` hỏi → trả lời + nguồn | Working |
| 1 · Gate | Similarity thấp hoặc Gemini `grounded=false` → không bịa | Working |
| 2 · Routing | Tag `@Mentor` khi không đủ căn cứ + lưu `Pending` | Working |
| 2 · Routing | `/pending` xem hàng đợi · `/resolve` đóng câu hỏi | Working |
| 3 · Signal | Cron 15 phút escalate Pending quá X giờ | Working |
| 3 · Signal | `/digest` tóm tắt hàng đợi cho Mentor | Working |
| — | `/tomtat` tóm tắt hội thoại kênh | Working |
| — | CLI test + `python -m bot.run_eval` | Working |

AI quyết định: **có đủ căn cứ trong knowledge để trả lời hay phải chuyển Mentor** — model `gemini-3.1-flash-lite`.

Chưa làm (non-goals MVP): thread merging, onboarding assistant, weekly digest đầy đủ (đã có digest hàng đợi).

## Chuẩn bị nhanh

### 1) Python env

```powershell
cd codebase
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### 2) Điền `.env`

- `GEMINI_API_KEY` — bắt buộc (test CLI cũng cần)
- `DISCORD_BOT_TOKEN` — bắt buộc khi chạy bot
- `DISCORD_GUILD_ID` — server ID
- `KNOWLEDGE_CHANNEL_IDS` — kênh FAQ/announcements bot được đọc
- `MENTOR_ROLE_ID` — role sẽ bị tag khi fallback
- `ASK_CHANNEL_ID` — (tuỳ chọn) giới hạn kênh được hỏi

### 3) Discord Developer Portal

1. Tạo Application → Bot → copy token
2. Bật **Message Content Intent**
3. OAuth2 URL Generator: scopes `bot` + `applications.commands`
4. Permissions: View Channel, Send Messages, Read Message History, Mention Everyone (nếu tag role; hoặc dùng role mentionable)
5. Mời bot vào server

### 4) Chạy thử không Discord (CP2/CP3)

```powershell
cd codebase
python -m bot.ask_cli --reindex "deadline nộp bài khi nào?"
python -m bot.ask_cli "nộp muộn bị trừ bao nhiêu?"
python -m bot.ask_cli "API key OpenAI của mentor là gì?"
```

Câu 1–2 nên grounded. Câu 3 nên fallback mentor.

### 5) Chạy bot Discord

```powershell
cd codebase
python -m bot.main
```

Trong server:

- `/ask question: deadline nộp bài khi nào?`
- `@BotName nộp muộn có sao không?`
- `/tomtat` — tóm tắt tin gần đây trong kênh
- `/pending` — Mentor xem câu chờ xử lý
- `/resolve id:1` — Mentor đánh dấu đã trả lời
- `/digest` — tóm tắt hàng đợi Pending cho Mentor
- `/sync_channels` — nạp lịch sử kênh kiến thức (cần Manage Server)
- `/reindex` — index lại file `knowledge/`

### 6) Chạy golden set (eval/)

```powershell
cd codebase
python -m bot.run_eval --reindex
```

Kết quả: `eval/results-round1.md` (dạng `X/22`).
## Cấu trúc

```
codebase/
  bot/
    config.py          # đọc .env
    rag.py             # chunk + retrieve (local JSON)
    gemini_client.py   # Gemini quyết định grounded
    pipeline.py        # nối RAG → trả lời / fallback
    db.py              # SQLite Pending/Resolved/Escalated
    ask_cli.py         # test CLI
    main.py            # Discord bot
  knowledge/           # nguồn sự thật seed (data giả)
  .env.example
  requirements.txt
```

## Lưu ý hackathon

- Không commit file `.env` / token.
- `knowledge/` hiện là **data giả** để demo; khi có kênh Discord thật dùng `/sync_channels`.
- Pack `data/vlearn-pack/` chỉ dùng mining/golden set — **không** commit trích dẫn dài vào repo nộp.
