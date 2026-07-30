# Tài Liệu Kỹ Thuật: Hệ Thống Bot Điều Phối & Quản Lý Tri Thức Discord

## 1. Tầm nhìn & Cốt lõi hệ thống (Founder Mindset)
* **Định vị:** Bot không hoạt động như một cỗ máy "trả lời vạn năng" (tránh Halucination - bịa thông tin). Đây là một **Hệ thống điều phối cuộc trò chuyện (Conversation Routing System)**.
* **Sứ mệnh:** Định tuyến đúng tri thức, đến đúng người, vào đúng thời điểm. Đảm bảo mọi "tín hiệu" (câu hỏi, thắc mắc) của người dùng không bao giờ bị rơi vào im lặng.

---

## 2. Kiến trúc Giải pháp (3 Lớp Chức Năng)

### Lớp 1: Trả lời tự động (Knowledge Layer - RAG)
* Hoạt động như một Agent thu thập và lập chỉ mục (index) toàn bộ tin nhắn/tài liệu đã được ghim trong kênh FAQ.
* Khi có câu hỏi mới: AI phân tích ngữ nghĩa, nếu trùng khớp với dữ liệu đã học $\rightarrow$ Trả lời tự động kèm link trỏ thẳng về nguồn gốc.
* **Cơ chế Fallback:** Nếu độ tự tin (Confidence score) của AI thấp, tuyệt đối không bịa câu trả lời, lập tức chuyển giao trạng thái sang Lớp 2.

### Lớp 2: Định tuyến đúng người (Routing Layer)
* **Smart Tagging:** Nhận diện câu hỏi ngoài vùng kiến thức $\rightarrow$ Phân tích từ khóa chủ đề $\rightarrow$ Tự động `@tag` đích danh Mentor hoặc TA phụ trách mảng đó.
* **Thread Merging (Gộp luồng):** Phát hiện câu hỏi có nội dung tương tự với một vấn đề đang được thảo luận nhưng chưa đóng (Unresolved) $\rightarrow$ Cung cấp link dẫn người hỏi sang Thread đó để tránh loãng kênh.
* **Onboarding Assistant:** Lắng nghe sự kiện người dùng mới join kênh $\rightarrow$ Phân tích câu hỏi đầu tiên hoặc role của họ $\rightarrow$ Gợi ý các tài liệu/kênh nhập môn phù hợp.

### Lớp 3: Giữ động lực & Cảnh báo (Signal Layer)
* **Timeout Alert:** Chạy ngầm các trình lập lịch (Cronjob). Nếu một câu hỏi/thread không có bất kỳ phản hồi nào sau `X` giờ $\rightarrow$ Agent tự động trồi lên nhắc nhở Mentor hoặc đẩy báo động (escalate) lên kênh của Ban quản trị.
* **Weekly/Daily Digest:** Tự động tổng hợp các câu hỏi chưa được giải quyết, hoặc các chủ đề "hot" nhất trong tuần gửi thành một báo cáo ngắn gọn cho Ban tổ chức theo dõi tiến độ hỗ trợ.

---

## 3. Tổng quan công nghệ (Tech Stack Nâng Cấp)
* **Ngôn ngữ lõi:** Python 3.10+
* **Giao tiếp Discord API:** `discord.py`
* **Xử lý lập lịch (Signal Layer):** `discord.ext.tasks` (Tích hợp sẵn để chạy ngầm đếm thời gian X giờ).
* **AI Engine:** `google-generativeai` (Gemini API xử lý logic phân loại intent và bóc tách từ khóa).
* **Database & RAG:** 
  * Cần tích hợp CSDL Vector (như `ChromaDB` hoặc `FAISS`) để lưu trữ và tìm kiếm ngữ nghĩa các tài liệu FAQ cho Lớp 1.
  * Sử dụng `MySQL` hoặc `SQLite` để lưu trạng thái của câu hỏi (Status: `Pending`, `Resolved`, `Escalated`, `Timestamp`).

---

## 4. Luồng thuật toán cốt lõi (Core Workflow)

1. **Lắng nghe sự kiện (Event Hook):** 
   * Bắt sự kiện `on_message` (khi có người chat) hoặc `on_member_join` (khi có người mới).
2. **Tiền xử lý & Phân loại (Intent Classification):** 
   * Gửi text sang Gemini phân tích xem đây là "Câu hỏi kỹ thuật", "Trò chuyện phiếm", hay "Yêu cầu hỗ trợ".
3. **Thực thi Lớp 1 (Truy xuất RAG):** 
   * Nếu là câu hỏi, tìm kiếm trong Vector DB. 
   * Nếu Độ chính xác > 80% $\rightarrow$ Trả lời + Link nguồn. 
   * Nếu Độ chính xác < 80% $\rightarrow$ Chuyển sang Bước 4.
4. **Thực thi Lớp 2 (Routing):** 
   * Ghi nhận ID tin nhắn vào MySQL với trạng thái `Pending`. 
   * Bot phản hồi: *"Câu hỏi này hơi khó, để mình tag Mentor chuyên môn hỗ trợ bạn nhé!"* $\rightarrow$ Lấy ID của Mentor tương ứng từ CSDL và `@tag`.
5. **Thực thi Lớp 3 (Tracking vòng lặp):** 
   * Task chạy ngầm quét MySQL mỗi 15 phút. 
   * Tìm các dòng `Pending` có `Timestamp` vượt quá thời gian quy định $\rightarrow$ Bắn tin nhắn cảnh báo vào kênh riêng của TA/Mentor.