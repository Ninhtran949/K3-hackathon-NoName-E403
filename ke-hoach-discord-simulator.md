# Kế hoạch xây dựng giao diện Discord giả lập và bot tóm tắt hội thoại

## 1. Mục tiêu dự án

Xây dựng một ứng dụng web mô phỏng giao diện của một server Discord. Ứng dụng có nhiều người dùng giả lập đang trò chuyện trong các kênh, cùng một bot có khả năng trả lời câu hỏi dựa trên nội dung hội thoại.

Tình huống sử dụng chính:

1. Nhiều thành viên trò chuyện trong một kênh.
2. Người dùng hiện tại rời khỏi kênh hoặc chưa đọc một số tin nhắn.
3. Khi quay lại, người dùng nhập câu hỏi như:

   ```text
   @SummaryBot tôi đã bỏ lỡ những nội dung gì?
   ```

4. Bot đọc phần tin nhắn chưa đọc và trả về nội dung tóm tắt.

Ứng dụng cần sử dụng:

- HTML để xây dựng cấu trúc giao diện.
- CSS để tạo bố cục và phong cách của ứng dụng chat.
- JavaScript để quản lý tin nhắn, người dùng giả lập, trạng thái chưa đọc và sự kiện gọi bot.

Phiên bản đầu tiên có thể chạy hoàn toàn trên trình duyệt mà không cần backend.

## 2. Phạm vi phiên bản đầu tiên

Ứng dụng bao gồm:

- Thanh danh sách server.
- Danh sách kênh chat.
- Khu vực hiển thị nội dung trò chuyện.
- Danh sách thành viên online và offline.
- Nhiều người dùng giả lập với avatar, tên và trạng thái riêng.
- Một bot tên `SummaryBot`.
- Ô nhập tin nhắn.
- Hỗ trợ tag `@SummaryBot`.
- Hiển thị số lượng tin nhắn chưa đọc.
- Bot có thể tóm tắt những tin nhắn người dùng chưa đọc.
- Lưu dữ liệu cơ bản bằng `localStorage`.

## 3. Cấu trúc thư mục đề xuất

```text
discord-simulator/
├── index.html
├── css/
│   ├── style.css
│   └── responsive.css
├── js/
│   ├── data.js
│   ├── app.js
│   ├── chat.js
│   ├── bot.js
│   └── simulator.js
└── assets/
    ├── avatars/
    └── icons/
```

Chức năng của từng file:

- `index.html`: Chứa khung giao diện chính.
- `css/style.css`: Chứa màu sắc, typography và bố cục desktop.
- `css/responsive.css`: Xử lý giao diện trên tablet và điện thoại.
- `js/data.js`: Chứa dữ liệu mẫu của users, channels và messages.
- `js/app.js`: Khởi tạo ứng dụng và quản lý trạng thái chung.
- `js/chat.js`: Gửi, hiển thị, lưu và đọc tin nhắn.
- `js/bot.js`: Nhận diện câu hỏi và tạo câu trả lời của bot.
- `js/simulator.js`: Tạo hội thoại tự động giữa các user giả lập.
- `assets/avatars/`: Chứa avatar người dùng và bot.
- `assets/icons/`: Chứa các biểu tượng sử dụng trong giao diện.

## 4. Thiết kế giao diện

### 4.1. Bố cục desktop

Giao diện được chia thành bốn phần:

```text
┌────────┬──────────────┬────────────────────────┬───────────────┐
│ Server │ Kênh chat    │ Nội dung trò chuyện    │ Thành viên    │
│ icons  │              │                        │               │
│        │ # general    │ Minh: Chào mọi người   │ Online        │
│        │ # project    │ Lan: Họp lúc 3 giờ     │ Minh          │
│        │ # random     │ Bot: ...               │ Lan           │
│        │              │                        │ SummaryBot    │
│        │ User profile │ [ Nhập tin nhắn... ]   │               │
└────────┴──────────────┴────────────────────────┴───────────────┘
```

### 4.2. Các thành phần giao diện

- Server sidebar.
- Channel sidebar.
- Header của kênh hiện tại.
- Danh sách tin nhắn.
- Ô nhập tin nhắn.
- Danh sách thành viên.
- Thông báo số tin chưa đọc.
- Trạng thái người dùng đang nhập.
- Trạng thái bot đang xử lý.

### 4.3. Các loại tin nhắn

Giao diện cần phân biệt:

- Tin nhắn của người dùng khác.
- Tin nhắn của người dùng hiện tại.
- Tin nhắn của bot.
- Tin nhắn có tag người dùng.
- Tin nhắn hệ thống.

### 4.4. Responsive

Trên màn hình nhỏ:

- Ẩn danh sách thành viên.
- Thu gọn danh sách server và channel.
- Cho phép mở sidebar bằng nút menu.
- Giữ ô nhập tin nhắn cố định phía dưới.

## 5. Mô hình dữ liệu

### 5.1. Người dùng

```js
const users = [
  {
    id: "user-1",
    name: "Minh",
    avatar: "assets/avatars/minh.png",
    status: "online",
    isBot: false
  },
  {
    id: "user-2",
    name: "Lan",
    avatar: "assets/avatars/lan.png",
    status: "online",
    isBot: false
  },
  {
    id: "bot-1",
    name: "SummaryBot",
    avatar: "assets/avatars/bot.png",
    status: "online",
    isBot: true
  }
];
```

### 5.2. Kênh chat

```js
const channels = [
  {
    id: "general",
    name: "general",
    description: "Kênh trò chuyện chung"
  },
  {
    id: "project",
    name: "project",
    description: "Trao đổi công việc dự án"
  }
];
```

### 5.3. Tin nhắn

```js
const messages = [
  {
    id: "message-101",
    channelId: "general",
    authorId: "user-1",
    content: "Chiều nay nhóm họp lúc 15 giờ nhé.",
    createdAt: "2026-07-30T14:20:00",
    mentions: []
  }
];
```

### 5.4. Trạng thái đã đọc

```js
const readState = {
  currentUserId: "current-user",
  channels: {
    general: {
      lastReadMessageId: "message-95"
    }
  }
};
```

Thuộc tính `lastReadMessageId` giúp ứng dụng xác định những tin nhắn nào người dùng chưa đọc.

## 6. Trạng thái ứng dụng

Có thể quản lý trạng thái chung bằng một object:

```js
const appState = {
  currentUserId: "current-user",
  activeChannelId: "general",
  users: [],
  channels: [],
  messages: [],
  readState: {},
  simulatorRunning: false,
  botTyping: false
};
```

Ở phiên bản Vanilla JavaScript, mỗi khi trạng thái thay đổi, ứng dụng gọi lại hàm render cho thành phần liên quan.

## 7. Luồng gửi tin nhắn

Khi người dùng nhấn Enter hoặc nút gửi:

1. Đọc nội dung từ ô nhập.
2. Loại bỏ khoảng trắng thừa.
3. Không xử lý nếu nội dung rỗng.
4. Tạo object tin nhắn mới.
5. Thêm tin nhắn vào channel hiện tại.
6. Render tin nhắn lên giao diện.
7. Tự động cuộn xuống cuối danh sách.
8. Kiểm tra tin nhắn có tag `@SummaryBot` hay không.
9. Nếu có tag bot, chuyển câu hỏi cho bộ xử lý bot.
10. Lưu trạng thái mới vào `localStorage`.

Mã giả:

```js
function sendMessage(content) {
  const normalizedContent = content.trim();

  if (!normalizedContent) {
    return;
  }

  const message = createMessage({
    authorId: appState.currentUserId,
    channelId: appState.activeChannelId,
    content: normalizedContent
  });

  addMessage(message);
  renderMessage(message);
  scrollChatToBottom();
  saveState();

  if (normalizedContent.includes("@SummaryBot")) {
    handleBotMention(message);
  }
}
```

## 8. Xử lý sự kiện gọi bot

Bot cần nhận biết các dạng câu hỏi:

- `@SummaryBot tóm tắt cuộc trò chuyện`
- `@SummaryBot tôi đã bỏ lỡ những gì?`
- `@SummaryBot có tin gì mới?`
- `@SummaryBot mọi người đã thống nhất điều gì?`
- `@SummaryBot ai nhắc đến buổi họp?`
- `@SummaryBot có vấn đề nào chưa được giải quyết?`

Luồng xử lý:

```js
async function handleBotMention(userMessage) {
  showBotTyping();

  const question = removeBotMention(userMessage.content);
  const unreadMessages = getUnreadMessages(
    userMessage.authorId,
    userMessage.channelId
  );

  const answer = generateBotAnswer(question, unreadMessages);

  await delay(1200);

  hideBotTyping();
  sendBotMessage(answer, userMessage.channelId);
}
```

## 9. Cách xác định tin nhắn chưa đọc

Quy trình:

1. Lấy `lastReadMessageId` của người dùng trong channel hiện tại.
2. Tìm vị trí của tin nhắn đó trong danh sách.
3. Lấy tất cả tin nhắn nằm phía sau.
4. Loại bỏ câu hỏi vừa dùng để gọi bot.
5. Có thể loại bỏ các tin nhắn bot cũ để tránh tóm tắt lặp lại.

```js
function getUnreadMessages(userId, channelId) {
  const channelMessages = appState.messages.filter(
    message => message.channelId === channelId
  );

  const lastReadMessageId =
    appState.readState[userId]?.[channelId]?.lastReadMessageId;

  const lastReadIndex = channelMessages.findIndex(
    message => message.id === lastReadMessageId
  );

  return channelMessages
    .slice(lastReadIndex + 1)
    .filter(message => !isCurrentBotQuestion(message));
}
```

## 10. Bot tóm tắt không sử dụng AI

Trong phiên bản đầu tiên, bot có thể tóm tắt dựa trên quy tắc.

### 10.1. Các bước xử lý

1. Nhận danh sách tin nhắn chưa đọc.
2. Loại bỏ tin nhắn của bot.
3. Đếm số lượng tin nhắn và người tham gia.
4. Tìm các từ khóa quan trọng.
5. Nhóm tin nhắn theo chủ đề.
6. Sinh câu trả lời theo mẫu.

### 10.2. Nhóm chủ đề đề xuất

- Cuộc họp và thời gian.
- Công việc được giao.
- Deadline.
- Quyết định đã thống nhất.
- Lỗi hoặc vấn đề cần giải quyết.
- Tài liệu và đường dẫn được chia sẻ.

Ví dụ danh sách từ khóa:

```js
const topicKeywords = {
  meeting: ["họp", "meeting", "trao đổi", "15 giờ", "16 giờ"],
  deadline: ["deadline", "hạn", "thứ sáu", "ngày mai"],
  task: ["phụ trách", "hoàn thành", "làm", "kiểm tra"],
  issue: ["lỗi", "bug", "không hoạt động", "401", "500"],
  decision: ["thống nhất", "quyết định", "chốt"],
  document: ["tài liệu", "file", "link", "thiết kế"]
};
```

### 10.3. Kết quả mẫu

```text
Bạn đã bỏ lỡ 12 tin nhắn từ 4 thành viên.

Tóm tắt:
• Nhóm thống nhất họp lúc 15:00 hôm nay.
• Minh sẽ hoàn thành giao diện đăng nhập.
• Lan phụ trách kiểm tra API.
• Deadline bản demo là thứ Sáu.

Nội dung cần chú ý:
• API đăng nhập hiện đang trả về lỗi 401.
```

Nếu không có tin nhắn chưa đọc:

```text
Bạn không bỏ lỡ tin nhắn nào trong kênh này.
```

## 11. Phân loại ý định câu hỏi

Bot có thể dùng một hàm đơn giản để xác định người dùng muốn hỏi gì:

```js
function detectIntent(question) {
  const text = question.toLowerCase();

  if (
    text.includes("tóm tắt") ||
    text.includes("bỏ lỡ") ||
    text.includes("tin gì mới")
  ) {
    return "summary";
  }

  if (text.includes("thống nhất") || text.includes("quyết định")) {
    return "decisions";
  }

  if (text.includes("vấn đề") || text.includes("lỗi")) {
    return "issues";
  }

  if (text.includes("ai") && text.includes("họp")) {
    return "meeting_author";
  }

  return "unknown";
}
```

Nếu không nhận diện được câu hỏi, bot có thể trả lời:

```text
Mình chưa hiểu rõ câu hỏi. Bạn có thể yêu cầu:
• Tóm tắt những tin nhắn chưa đọc
• Liệt kê các quyết định
• Liệt kê vấn đề đang được thảo luận
• Tìm người đã nhắc đến cuộc họp
```

## 12. Hội thoại giả lập

File `simulator.js` chứa các kịch bản trò chuyện có sẵn:

```js
const conversationScenario = [
  {
    delay: 1000,
    userId: "user-1",
    channelId: "general",
    content: "Chiều nay chúng ta họp lúc 15 giờ nhé."
  },
  {
    delay: 2500,
    userId: "user-2",
    channelId: "general",
    content: "Mình sẽ chuẩn bị bản thiết kế."
  },
  {
    delay: 4000,
    userId: "user-3",
    channelId: "general",
    content: "API đăng nhập vẫn còn lỗi 401."
  }
];
```

JavaScript lần lượt phát các tin nhắn theo `delay`.

Các nút điều khiển nên có:

- Bắt đầu hội thoại giả lập.
- Tạm dừng hội thoại.
- Khởi động lại kịch bản.
- Đánh dấu tất cả đã đọc.
- Giả lập người dùng rời khỏi kênh.
- Giả lập người dùng quay lại.

## 13. Quản lý trạng thái chưa đọc

Khi người dùng đang xem một channel:

- Tin nhắn mới có thể tự động được đánh dấu đã đọc nếu cửa sổ đang được focus và người dùng đã cuộn xuống cuối.
- Nếu người dùng đang ở channel khác, tăng bộ đếm chưa đọc.
- Nếu người dùng đã rời ứng dụng, tất cả tin nhắn mới được tính là chưa đọc.

Ví dụ:

```js
function receiveMessage(message) {
  addMessage(message);

  const isActiveChannel =
    message.channelId === appState.activeChannelId;

  const canMarkAsRead =
    isActiveChannel &&
    document.hasFocus() &&
    isChatScrolledToBottom();

  if (canMarkAsRead) {
    markMessageAsRead(message);
  } else {
    increaseUnreadCount(message.channelId);
  }

  renderApp();
}
```

## 14. Lưu dữ liệu bằng localStorage

Dữ liệu nên được lưu:

- Tin nhắn.
- Channel hiện tại.
- Trạng thái đọc.
- Trạng thái chạy của simulator.

```js
function saveState() {
  localStorage.setItem(
    "discordSimulatorState",
    JSON.stringify(appState)
  );
}

function loadState() {
  const savedState = localStorage.getItem(
    "discordSimulatorState"
  );

  return savedState ? JSON.parse(savedState) : null;
}
```

Nên có nút “Đặt lại dữ liệu” để quay về kịch bản ban đầu.

## 15. Các giai đoạn triển khai

### Giai đoạn 1: Dựng giao diện

- Tạo bố cục bốn cột.
- Thiết kế dark theme.
- Tạo component channel.
- Tạo component tin nhắn.
- Tạo component thành viên.
- Tạo ô nhập tin nhắn.
- Làm responsive.

Kết quả: giao diện tĩnh hoàn chỉnh.

### Giai đoạn 2: Quản lý dữ liệu chat

- Khai báo users, channels và messages.
- Render dữ liệu bằng JavaScript.
- Cho phép chuyển channel.
- Cho phép gửi tin nhắn.
- Tự động cuộn xuống tin nhắn mới.
- Hiển thị timestamp.

Kết quả: người dùng có thể sử dụng ứng dụng chat cơ bản.

### Giai đoạn 3: Mô phỏng nhiều người dùng

- Tạo danh sách hội thoại mẫu.
- Phát tin nhắn theo thời gian.
- Hiển thị trạng thái đang nhập.
- Cho phép bắt đầu và tạm dừng mô phỏng.
- Cập nhật số tin nhắn chưa đọc.

Kết quả: server có cảm giác đang hoạt động với nhiều thành viên.

### Giai đoạn 4: Xây dựng bot

- Nhận diện tag `@SummaryBot`.
- Tách câu hỏi khỏi phần tag.
- Phân loại ý định.
- Lấy đúng phạm vi tin nhắn chưa đọc.
- Tóm tắt theo quy tắc.
- Hiển thị trạng thái bot đang xử lý.
- Gửi câu trả lời vào channel.

Kết quả: bot có thể trả lời câu hỏi về nội dung người dùng đã bỏ lỡ.

### Giai đoạn 5: Lưu trữ và hoàn thiện

- Lưu dữ liệu bằng `localStorage`.
- Khôi phục dữ liệu khi tải lại trang.
- Thêm emoji và reply.
- Thêm thông báo mention.
- Kiểm tra giao diện desktop và mobile.
- Xử lý các trường hợp dữ liệu trống hoặc không hợp lệ.

## 16. Các trường hợp kiểm thử

### Gửi tin nhắn

- Không gửi tin nhắn rỗng.
- Nhấn Enter gửi được tin nhắn.
- `Shift + Enter` xuống dòng.
- Tin nhắn hiển thị đúng người gửi và thời gian.

### Gọi bot

- Tag đúng `@SummaryBot` thì bot phản hồi.
- Không tag bot thì không kích hoạt bot.
- Bot không tự phản hồi lại tin nhắn của chính nó.
- Bot hiển thị trạng thái đang nhập.
- Bot xử lý trường hợp không có tin chưa đọc.

### Tóm tắt

- Chỉ lấy tin nhắn sau `lastReadMessageId`.
- Không đưa câu hỏi gọi bot vào nội dung tóm tắt.
- Không lặp lại câu trả lời cũ của bot.
- Hiển thị đúng số tin nhắn và số người tham gia.
- Phát hiện được chủ đề họp, deadline, nhiệm vụ và vấn đề.

### Trạng thái chưa đọc

- Tin ở channel khác làm tăng số chưa đọc.
- Mở channel cập nhật trạng thái đọc.
- Tải lại trang không làm mất trạng thái.
- Người dùng quay lại có thể hỏi bot về phần đã bỏ lỡ.

### Responsive

- Giao diện không tràn chiều ngang.
- Ô nhập tin nhắn luôn sử dụng được.
- Sidebar mở và đóng đúng trên điện thoại.

## 17. Tiêu chí hoàn thành

Phiên bản đầu tiên được xem là hoàn thành khi:

- Giao diện mô phỏng một server Discord rõ ràng.
- Có ít nhất năm người dùng giả lập và một bot.
- Có ít nhất ba channel.
- Người dùng gửi được tin nhắn.
- Các user giả lập tự trò chuyện được.
- Channel hiển thị số tin nhắn chưa đọc.
- Tag `@SummaryBot` kích hoạt bot.
- Bot chỉ tóm tắt phần hội thoại người dùng đã bỏ lỡ.
- Bot xử lý được một số câu hỏi theo chủ đề.
- Dữ liệu vẫn tồn tại sau khi tải lại trang.
- Ứng dụng hoạt động được mà không cần server.
- Giao diện sử dụng được trên desktop và điện thoại.

## 18. Hướng phát triển sử dụng AI thật

Phiên bản nâng cao có thể sử dụng một mô hình AI để:

- Hiểu câu hỏi tự nhiên.
- Tóm tắt hội thoại chính xác hơn.
- Nhận biết quyết định, vấn đề và nhiệm vụ.
- Trả lời câu hỏi chi tiết dựa trên lịch sử chat.

Kiến trúc đề xuất:

```text
Trình duyệt
    │
    │ POST /api/bot/answer
    ▼
Node.js/Express backend
    │
    │ Gửi câu hỏi và các tin nhắn liên quan
    ▼
AI API
    │
    ▼
Backend trả kết quả cho trình duyệt
```

Payload mẫu:

```json
{
  "question": "Tôi đã bỏ lỡ những gì?",
  "channelId": "general",
  "messages": [
    {
      "author": "Minh",
      "content": "Chiều nay nhóm họp lúc 15 giờ."
    },
    {
      "author": "Lan",
      "content": "Mình sẽ chuẩn bị bản thiết kế."
    }
  ]
}
```

Lưu ý bảo mật:

- Không đặt khóa API trong JavaScript phía trình duyệt.
- Khóa API phải được lưu trong biến môi trường của backend.
- Backend cần kiểm tra dữ liệu đầu vào.
- Chỉ gửi những tin nhắn cần thiết cho AI.
- Cần giới hạn độ dài lịch sử chat để kiểm soát chi phí.

## 19. Thứ tự phát triển khuyến nghị

Thứ tự thực hiện:

1. Hoàn thành giao diện tĩnh.
2. Render users, channels và messages từ dữ liệu JavaScript.
3. Làm chức năng gửi tin nhắn.
4. Thêm hội thoại giả lập.
5. Thêm trạng thái chưa đọc.
6. Xây dựng bot dựa trên quy tắc.
7. Thêm `localStorage`.
8. Kiểm thử các luồng chính.
9. Tối ưu responsive.
10. Sau khi phiên bản cơ bản ổn định, cân nhắc tích hợp AI qua backend.

Với cách chia này, mỗi giai đoạn đều tạo ra một phiên bản có thể chạy và kiểm thử độc lập.
