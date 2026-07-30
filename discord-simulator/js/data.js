(function () {
  "use strict";

  const users = [
    {
      id: "current-user",
      name: "Bạn",
      initials: "B",
      color: "#7c6cf2",
      status: "online",
      activity: "Đang xem #general",
      isBot: false
    },
    {
      id: "user-1",
      name: "Minh",
      initials: "MI",
      color: "#ef7b67",
      status: "online",
      activity: "Đang hoàn thiện frontend",
      isBot: false
    },
    {
      id: "user-2",
      name: "Lan",
      initials: "LA",
      color: "#4bb6a5",
      status: "online",
      activity: "Đang kiểm tra API",
      isBot: false
    },
    {
      id: "user-3",
      name: "Huy",
      initials: "HU",
      color: "#e5a84b",
      status: "idle",
      activity: "Vắng mặt 5 phút",
      isBot: false
    },
    {
      id: "user-4",
      name: "Mai",
      initials: "MA",
      color: "#eb71ad",
      status: "online",
      activity: "Đang làm slide demo",
      isBot: false
    },
    {
      id: "user-5",
      name: "Khoa",
      initials: "KH",
      color: "#5b9bf0",
      status: "offline",
      activity: "Ngoại tuyến",
      isBot: false
    },
    {
      id: "bot-1",
      name: "SummaryBot",
      initials: "✦",
      color: "#7c6cf2",
      status: "online",
      activity: "Sẵn sàng tóm tắt",
      isBot: true
    }
  ];

  const channels = [
    {
      id: "general",
      name: "general",
      description: "Kênh trò chuyện chung của đội"
    },
    {
      id: "project",
      name: "project-alpha",
      description: "Trao đổi công việc và tiến độ dự án"
    },
    {
      id: "design",
      name: "design-review",
      description: "Góp ý giao diện và trải nghiệm người dùng"
    },
    {
      id: "random",
      name: "random",
      description: "Chuyện bên lề và năng lượng tích cực"
    }
  ];

  const messages = [
    {
      id: "general-000",
      channelId: "general",
      authorId: "bot-1",
      content: "Xin chào! Khi quay lại sau một khoảng thời gian, bạn chỉ cần gõ @SummaryBot tôi đã bỏ lỡ những gì? để nhận bản tóm tắt.",
      createdAt: "2026-07-30T08:30:00+07:00",
      mentions: []
    },
    {
      id: "general-001",
      channelId: "general",
      authorId: "user-1",
      content: "Chào cả đội! Mình vừa đẩy bản giao diện mới lên nhánh develop rồi nhé.",
      createdAt: "2026-07-30T08:35:00+07:00",
      mentions: []
    },
    {
      id: "general-002",
      channelId: "general",
      authorId: "current-user",
      content: "Tuyệt, mình sẽ xem qua trước buổi họp.",
      createdAt: "2026-07-30T08:38:00+07:00",
      mentions: []
    },
    {
      id: "general-003",
      channelId: "general",
      authorId: "user-2",
      content: "Chiều nay chúng ta họp lúc 15:00 nhé. Mình đã gửi lịch cho mọi người.",
      createdAt: "2026-07-30T09:02:00+07:00",
      mentions: []
    },
    {
      id: "general-004",
      channelId: "general",
      authorId: "user-3",
      content: "API đăng nhập vẫn trả về lỗi 401 khi token hết hạn, mình đang kiểm tra.",
      createdAt: "2026-07-30T09:05:00+07:00",
      mentions: []
    },
    {
      id: "general-005",
      channelId: "general",
      authorId: "user-4",
      content: "Mình sẽ hoàn thành slide demo trước 14:00. Deadline chốt bản cuối là thứ Sáu.",
      createdAt: "2026-07-30T09:08:00+07:00",
      mentions: []
    },
    {
      id: "general-006",
      channelId: "general",
      authorId: "user-1",
      content: "Thống nhất dùng phương án đăng nhập bằng magic link cho bản demo nhé.",
      createdAt: "2026-07-30T09:12:00+07:00",
      mentions: []
    },
    {
      id: "general-007",
      channelId: "general",
      authorId: "user-2",
      content: "@Bạn nhớ kiểm tra lại luồng onboarding trước cuộc họp nha.",
      createdAt: "2026-07-30T09:14:00+07:00",
      mentions: ["current-user"]
    },
    {
      id: "general-008",
      channelId: "general",
      authorId: "user-3",
      content: "Mình đã tái hiện được lỗi: request refresh token bị gửi hai lần khi người dùng mở lại tab.",
      createdAt: "2026-07-30T09:18:00+07:00",
      mentions: []
    },
    {
      id: "general-009",
      channelId: "general",
      authorId: "user-1",
      content: "Vậy Huy phụ trách sửa phần refresh token, mình sẽ hỗ trợ review pull request.",
      createdAt: "2026-07-30T09:21:00+07:00",
      mentions: []
    },
    {
      id: "general-010",
      channelId: "general",
      authorId: "user-4",
      content: "Mình vừa thêm biểu đồ retention vào slide. Mọi người xem giúp số liệu có dễ hiểu không nhé.",
      createdAt: "2026-07-30T09:25:00+07:00",
      mentions: []
    },
    {
      id: "general-011",
      channelId: "general",
      authorId: "user-2",
      content: "Biểu đồ ổn rồi. Mình đề xuất thêm một câu giải thích vì sao tuần thứ hai giảm.",
      createdAt: "2026-07-30T09:28:00+07:00",
      mentions: []
    },
    {
      id: "general-012",
      channelId: "general",
      authorId: "user-1",
      content: "Đã chốt: demo gồm đăng nhập, onboarding và trang tổng quan. Phần thông báo để sprint sau.",
      createdAt: "2026-07-30T09:32:00+07:00",
      mentions: []
    },
    {
      id: "general-013",
      channelId: "general",
      authorId: "user-3",
      content: "Mình cần thêm tài khoản test có quyền admin để kiểm tra trang tổng quan.",
      createdAt: "2026-07-30T09:36:00+07:00",
      mentions: []
    },
    {
      id: "general-014",
      channelId: "general",
      authorId: "user-2",
      content: "Mình đã tạo tài khoản test và gửi thông tin trong tài liệu nội bộ.",
      createdAt: "2026-07-30T09:39:00+07:00",
      mentions: []
    },
    {
      id: "general-015",
      channelId: "general",
      authorId: "user-4",
      content: "Checklist demo còn ba mục: empty state, loading skeleton và thông báo lỗi mạng.",
      createdAt: "2026-07-30T09:43:00+07:00",
      mentions: []
    },
    {
      id: "general-016",
      channelId: "general",
      authorId: "user-1",
      content: "Mình nhận phần loading skeleton. Mai giúp mình kiểm tra empty state trên mobile nhé.",
      createdAt: "2026-07-30T09:47:00+07:00",
      mentions: []
    },
    {
      id: "general-017",
      channelId: "general",
      authorId: "user-4",
      content: "Được nhé, mình sẽ hoàn thành kiểm tra responsive trước 13:30.",
      createdAt: "2026-07-30T09:50:00+07:00",
      mentions: []
    },
    {
      id: "general-018",
      channelId: "general",
      authorId: "user-3",
      content: "Tin vui: lỗi 401 đã sửa xong ở local. Mình đang chạy lại test trước khi đẩy code.",
      createdAt: "2026-07-30T09:55:00+07:00",
      mentions: []
    },
    {
      id: "general-019",
      channelId: "general",
      authorId: "user-2",
      content: "Nhớ cập nhật changelog và gắn link pull request vào bảng công việc nhé.",
      createdAt: "2026-07-30T09:58:00+07:00",
      mentions: []
    },
    {
      id: "general-020",
      channelId: "general",
      authorId: "user-1",
      content: "Cả đội tập trung lúc 14:45 để chuẩn bị, 15:00 bắt đầu chạy thử demo.",
      createdAt: "2026-07-30T10:02:00+07:00",
      mentions: []
    },
    {
      id: "general-021",
      channelId: "general",
      authorId: "user-1",
      content: "Mình để hướng dẫn chạy dự án bằng local server ở đây. Phần này có cả cách kiểm tra trên điện thoại: https://developer.mozilla.org/en-US/docs/Learn/Common_questions/Tools_and_setup/set_up_a_local_testing_server",
      createdAt: "2026-07-30T10:06:00+07:00",
      mentions: []
    },
    {
      id: "general-022",
      channelId: "general",
      authorId: "user-2",
      content: "Nếu cần xử lý lỗi xác thực 401, mọi người xem giải thích và checklist HTTP tại: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401",
      createdAt: "2026-07-30T10:10:00+07:00",
      mentions: []
    },
    {
      id: "project-001",
      channelId: "project",
      authorId: "user-1",
      content: "Sprint này ưu tiên luồng đăng nhập và trang tổng quan.",
      createdAt: "2026-07-30T08:12:00+07:00",
      mentions: []
    },
    {
      id: "project-002",
      channelId: "project",
      authorId: "user-4",
      content: "Mình đã cập nhật bảng phân công trong tài liệu dự án.",
      createdAt: "2026-07-30T08:18:00+07:00",
      mentions: []
    },
    {
      id: "project-003",
      channelId: "project",
      authorId: "user-2",
      content: "Mình chia API thành ba nhóm: xác thực, hồ sơ người dùng và dữ liệu dashboard.",
      createdAt: "2026-07-30T08:25:00+07:00",
      mentions: []
    },
    {
      id: "project-004",
      channelId: "project",
      authorId: "user-3",
      content: "Endpoint hồ sơ đã xong, endpoint dashboard còn thiếu bộ lọc theo tuần.",
      createdAt: "2026-07-30T08:31:00+07:00",
      mentions: []
    },
    {
      id: "project-005",
      channelId: "project",
      authorId: "user-1",
      content: "Minh nhận tích hợp dashboard, Lan kiểm tra contract API trước buổi họp.",
      createdAt: "2026-07-30T08:36:00+07:00",
      mentions: []
    },
    {
      id: "project-006",
      channelId: "project",
      authorId: "user-4",
      content: "Mình đã gắn link prototype và checklist nghiệm thu vào tài liệu dự án.",
      createdAt: "2026-07-30T08:42:00+07:00",
      mentions: []
    },
    {
      id: "project-007",
      channelId: "project",
      authorId: "user-2",
      content: "Deadline code freeze là 12:00 thứ Sáu để còn thời gian kiểm thử.",
      createdAt: "2026-07-30T08:49:00+07:00",
      mentions: []
    },
    {
      id: "project-008",
      channelId: "project",
      authorId: "user-3",
      content: "Hiện còn một bug khi bộ lọc ngày trả về danh sách trống.",
      createdAt: "2026-07-30T08:55:00+07:00",
      mentions: []
    },
    {
      id: "project-009",
      channelId: "project",
      authorId: "user-1",
      content: "Thống nhất hiển thị empty state thay vì báo lỗi nếu khoảng ngày không có dữ liệu.",
      createdAt: "2026-07-30T09:01:00+07:00",
      mentions: []
    },
    {
      id: "project-010",
      channelId: "project",
      authorId: "user-4",
      content: "Mình sẽ cập nhật nội dung empty state theo quyết định này.",
      createdAt: "2026-07-30T09:06:00+07:00",
      mentions: []
    },
    {
      id: "design-001",
      channelId: "design",
      authorId: "user-4",
      content: "Bản thiết kế mới đã tăng độ tương phản của nút chính.",
      createdAt: "2026-07-30T08:45:00+07:00",
      mentions: []
    },
    {
      id: "design-002",
      channelId: "design",
      authorId: "user-1",
      content: "Khoảng cách giữa biểu đồ và thẻ số liệu trên mobile hơi chật.",
      createdAt: "2026-07-30T08:50:00+07:00",
      mentions: []
    },
    {
      id: "design-003",
      channelId: "design",
      authorId: "user-4",
      content: "Mình sẽ tăng spacing lên 16px và giữ một cột dưới màn hình 640px.",
      createdAt: "2026-07-30T08:53:00+07:00",
      mentions: []
    },
    {
      id: "design-004",
      channelId: "design",
      authorId: "user-2",
      content: "Thông báo lỗi cần nói rõ người dùng nên thử lại hay liên hệ hỗ trợ.",
      createdAt: "2026-07-30T08:57:00+07:00",
      mentions: []
    },
    {
      id: "design-005",
      channelId: "design",
      authorId: "user-4",
      content: "Đã chốt dùng nút Thử lại cho lỗi mạng và giữ dữ liệu người dùng vừa nhập.",
      createdAt: "2026-07-30T09:03:00+07:00",
      mentions: []
    },
    {
      id: "design-006",
      channelId: "design",
      authorId: "user-3",
      content: "Mình sẽ bổ sung mã lỗi vào log, không hiển thị mã kỹ thuật trên giao diện.",
      createdAt: "2026-07-30T09:09:00+07:00",
      mentions: []
    },
    {
      id: "design-007",
      channelId: "design",
      authorId: "user-1",
      content: "Loading skeleton đã khớp với kích thước thẻ thật, tránh bị nhảy layout.",
      createdAt: "2026-07-30T09:15:00+07:00",
      mentions: []
    },
    {
      id: "design-008",
      channelId: "design",
      authorId: "user-4",
      content: "@Bạn xem giúp phiên bản mobile trong file thiết kế trước 13:00 nhé.",
      createdAt: "2026-07-30T09:22:00+07:00",
      mentions: ["current-user"]
    },
    {
      id: "random-001",
      channelId: "random",
      authorId: "user-3",
      content: "Ai cần cà phê trước buổi họp không? ☕",
      createdAt: "2026-07-30T09:20:00+07:00",
      mentions: []
    },
    {
      id: "random-002",
      channelId: "random",
      authorId: "user-4",
      content: "Cho mình một latte ít đá nhé ☕",
      createdAt: "2026-07-30T09:23:00+07:00",
      mentions: []
    },
    {
      id: "random-003",
      channelId: "random",
      authorId: "user-1",
      content: "Ai đoán đúng số bug còn lại sẽ được chọn món tráng miệng.",
      createdAt: "2026-07-30T09:26:00+07:00",
      mentions: []
    },
    {
      id: "random-004",
      channelId: "random",
      authorId: "user-2",
      content: "Mình đoán là hai, và hy vọng cả hai đều không nằm ở API 😄",
      createdAt: "2026-07-30T09:29:00+07:00",
      mentions: []
    },
    {
      id: "random-005",
      channelId: "random",
      authorId: "user-3",
      content: "Sau buổi demo mình gửi playlist tập trung của team nhé.",
      createdAt: "2026-07-30T09:34:00+07:00",
      mentions: []
    },
    {
      id: "random-006",
      channelId: "random",
      authorId: "user-4",
      content: "Deal! Nhưng trước mắt mọi người nhớ ăn trưa đúng giờ.",
      createdAt: "2026-07-30T09:38:00+07:00",
      mentions: []
    }
  ];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function createInitialState() {
    return {
      dataVersion: 3,
      currentUserId: "current-user",
      activeChannelId: "general",
      users: clone(users),
      channels: clone(channels),
      messages: clone(messages),
      readState: {
        "current-user": {
          general: { lastReadMessageId: "general-002" },
          project: { lastReadMessageId: "project-001" },
          design: { lastReadMessageId: "design-001" },
          random: { lastReadMessageId: null }
        }
      },
      simulatorRunning: false,
      simulatorIndex: 0,
      botTyping: false,
      typingUserId: null,
      userAway: false,
      replyingTo: null
    };
  }

  window.DiscordSimulatorData = {
    createInitialState
  };
})();
