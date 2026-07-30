# 1. AI trong sản phẩm quyết định điều gì và dùng model nào?

**AI quyết định câu hỏi logistics/FAQ này có đủ căn cứ trong knowledge (FAQ/kênh đã index) để trả lời hay phải chuyển Mentor/TA — dùng `gemini-3.1-flash-lite`.**

- Bài toán: grounded vs escalate (không bịa deadline/link/điểm).
- Model: `GEMINI_MODEL=gemini-3.1-flash-lite` (Gemini API qua `google-genai`).
- Gate kép: similarity RAG thấp **hoặc** model trả `grounded=false` → fallback tag Mentor.
