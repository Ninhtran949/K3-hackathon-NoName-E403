Hãy đóng vai một Senior Backend Developer. Dưới đây là file spec.md của dự án MVP 1.5 ngày. Nhiệm vụ của bạn là thiết kế và khởi tạo cấu trúc thư mục (Phase 0) cho tôi bằng Python.

Yêu cầu bắt buộc về kiến trúc (Strict Constraints):

Clean Architecture / Ports & Adapters: Áp dụng triệt để để đảm bảo tính độc lập hệ thống (mục tiêu: 'không focus only vào Discord').

Tách biệt giao diện: Lớp Adapter (Discord listener sử dụng discord.py) KHÔNG được chứa logic AI, RAG hay Database. Nó chỉ làm nhiệm vụ parse event và format kết quả trả về.

Đóng gói Core Logic: Toàn bộ logic nhúng text (Embedding), truy vấn ChromaDB, gọi Gemini API, xử lý confidence score phải được đóng gói vào module Core_RAG_Engine.

Giao tiếp (Communication): Các module từ ngoài (Discord) gọi vào Core phải thông qua interface/function call thuần túy (ưu tiên Dependency Injection nếu cần).

Tách biệt Config/Prompt: Phải có thư mục riêng biệt để lưu trữ file cấu hình routing (JSON/YAML) và System Prompts, tuyệt đối không hard-code vào logic Python.

Định dạng đầu ra (Output Format):

Trình bày cấu trúc thư mục dưới dạng ASCII Tree.

Cung cấp nội dung file requirements.txt chứa các thư viện cốt lõi cần cài đặt.

Cung cấp nội dung file .env.example liệt kê các biến môi trường cần thiết (API Keys, Token...).

Giải thích ngắn gọn (1 dòng) vai trò của từng thư mục cấp 1 và cấp 2. Không sinh ra code implement chi tiết ở phase này.
