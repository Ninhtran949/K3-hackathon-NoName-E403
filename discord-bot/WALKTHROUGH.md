# Walkthrough — Build Phase Discord Bot P0

Ngày xác minh: 2026-07-30

## Phạm vi đã hoàn thành

### Story 1 — Hỏi đáp có nguồn

1. Người dùng hỏi bằng `/ask`, mention bot hoặc câu kết thúc bằng `?` trong kênh
   Q&A allowlist.
2. Bot chỉ tải source từ các kênh người hỏi có `View Channel` và
   `Read Message History`.
3. Lexical retrieval tiếng Việt áp dụng hard similarity gate trước khi gọi AI.
4. Claude trả strict tool output gồm answer, confidence, topic và source IDs.
5. Pipeline đối chiếu toàn bộ source ID với context backend.
6. Trước khi gửi, bot fetch lại từng Discord message, kiểm tra permission lần nữa
   và tự hủy câu trả lời nếu source đã sửa/xóa.
7. Link Discord do backend lấy từ message thật, không nhận URL do LLM tạo.

### Story 2 — Ingest nguồn được phép

- Chỉ ingest chính xác Channel/Thread ID nằm trong allowlist.
- Bỏ qua bot, webhook, câu hỏi, emoji-only, tin quá ngắn và credential.
- Lưu author, role IDs, timestamp, channel, jump URL, pinned/important/official.
- Message edit dùng upsert; edit thành nội dung không hợp lệ sẽ xóa source cũ.
- Single delete và bulk delete đều xóa source.
- Private thread không được ingest hoặc trích dẫn trong P0.
- Community source hết hạn được cleanup lúc startup và mỗi 24 giờ.

### Story 3 — Human escalation

- No source, source yếu, conflict, AI unavailable và source validation failure đều
  đi vào cùng một luồng escalation.
- Keyword router chọn topic/role; role ID chỉ hợp lệ nếu nằm trong allowlist role.
- Support case idempotent được lưu SQLite và đăng vào channel hỗ trợ.
- Chỉ ping đúng role đã xác minh bằng per-message `AllowedMentions`.
- Mentor/admin/default support role dùng `👀` và `✅` để cập nhật trạng thái.
- Conflict về deadline/ngày giờ ưu tiên route cho admin.
- Support case `resolved` được xóa sau thời hạn cấu hình.

## Hardening đã áp dụng

- `/ask` và hỏi tự động bị chặn ngoài kênh Q&A.
- Slash reply mặc định ephemeral.
- Credential guard chặn API key, token, password trước khi lưu/gọi AI/route.
- Community question không thể trở thành source cho câu hỏi sau.
- Không dùng dữ liệu demo hoặc deadline trong spec làm sự thật.
- Strict Anthropic schema chỉ dùng JSON Schema subset được API hỗ trợ; constraint
  độ dài/pattern được kiểm tra lại trong code.
- Không đặt `temperature` cho Claude Sonnet 5.
- Provider error log chỉ chứa loại lỗi/status/request ID, không chứa key hoặc prompt.

## Lệnh

| Lệnh | Quyền | Kết quả |
|---|---|---|
| `/ask` | Member trong kênh Q&A | Answer có nguồn hoặc tạo support case |
| `/help` | Member | Hướng dẫn và trạng thái SET/MISSING |
| `/admin-reindex` | Manage Server | Nạp lại tin allowlist |
| `/admin-test-route` | Manage Server | Kiểm tra topic và role đích |

Các lệnh starter `/ping`, `/hello`, `/userinfo`, `/note`, `/clear` vẫn hoạt động.

## Bằng chứng tự động

```text
pytest:              102 passed
ruff check:          All checks passed
ruff format --check: 29 files already formatted
compileall:           passed
pip check:            No broken requirements found
```

Anthropic SDK `0.117.1` đã được cài trong `.venv`.

SQLite migration live đã có `knowledge_sources` và `support_cases`. Cả hai đang có
0 bản ghi vì allowlist chưa được cấu hình và không có dữ liệu giả được seed.

## Cấu hình ngoài code còn bắt buộc

Hiện Discord token và test guild đã có, nhưng P0 chưa thể demo end-to-end cho đến
khi điền:

- `DISCORD_QA_CHANNEL_IDS`
- `DISCORD_ANNOUNCEMENT_CHANNEL_IDS`
- `DISCORD_SUPPORT_CHANNEL_ID`
- `DISCORD_ADMIN_ROLE_IDS`
- `DISCORD_MENTOR_ROLE_IDS`
- `DISCORD_DEFAULT_SUPPORT_ROLE_ID`
- `ANTHROPIC_API_KEY`
- `ENABLE_MESSAGE_CONTENT_INTENT=true`
- Role ID thật trong `config/routing.json`

Message Content Intent cũng phải bật trong Discord Developer Portal. Role cần
mentionable hoặc bot cần quyền mention role.

## Kịch bản xác minh thủ công sau khi điền config

1. Restart bot và xác nhận log đồng bộ 9 slash command.
2. Chạy `/help`; ba trạng thái nguồn, AI và hỗ trợ đều phải là `✅`.
3. Chạy `/admin-test-route` với câu Docker/CUDA/deadline.
4. Chạy `/admin-reindex`.
5. Hỏi một câu có thông báo official; kiểm tra answer và jump link.
6. Xóa/sửa thông báo rồi hỏi lại; bot không được dùng source cũ.
7. Hỏi câu ngoài corpus; kiểm tra support case và role ping.
8. Mentor react `👀`, sau đó `✅`; kiểm tra embed đổi trạng thái.
9. Hỏi hai nguồn deadline mâu thuẫn; bot không chọn bừa và phải route admin.

## Quyết định để phase sau

`/catchup` và `/important` là P1, chỉ triển khai sau khi checklist P0 ở trên chạy
end-to-end bằng dữ liệu thật. Vector retrieval cũng được hoãn cho đến khi team
chốt embedding provider, chi phí và chính sách dữ liệu.
