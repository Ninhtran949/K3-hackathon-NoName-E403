# K3 Mate — Discord Student Assistant Prototype

Prototype tương tác mô phỏng 3 luồng chính trong `spec.md`:

1. Trả lời câu hỏi có căn cứ và mở được nguồn trích dẫn.
2. Khi thiếu căn cứ, nói rõ giới hạn và chuyển đúng mentor theo từ khoá.
3. Tạo yêu cầu trong `#cần-hỗ-trợ` để mentor theo dõi và đánh dấu hoàn tất.

## Chạy local

```bash
npm install
npm run dev
```

Build production:

```bash
npm run build
npm run preview
```

## Trạng thái prototype

- Mức: **Mock tương tác**
- Dữ liệu: dữ liệu giả, không dùng dữ liệu học viên thật
- AI/RAG/Discord API: chưa kết nối; quyết định confidence và routing đang được mô phỏng ở `routeQuestion()` trong `src/App.jsx`
- Flow demo gợi ý: chọn **Hỏi deadline** → mở nguồn → chọn **Hỏi lỗi CUDA** → mở `#cần-hỗ-trợ` → đánh dấu đã xử lý
