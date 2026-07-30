(function () {
  "use strict";

  const scenario = [
    {
      delay: 900,
      userId: "user-1",
      channelId: "general",
      content: "Mình vừa cập nhật giao diện đăng nhập theo góp ý sáng nay."
    },
    {
      delay: 1400,
      userId: "user-2",
      channelId: "general",
      content: "API refresh token vẫn còn lỗi 401, mình sẽ phụ trách kiểm tra log."
    },
    {
      delay: 1300,
      userId: "user-4",
      channelId: "design",
      content: "File thiết kế mới đã có trạng thái loading và empty state rồi nhé."
    },
    {
      delay: 1500,
      userId: "user-3",
      channelId: "general",
      content: "Mọi người thống nhất họp lúc 15:00 hôm nay để chạy thử bản demo nhé."
    },
    {
      delay: 1200,
      userId: "user-4",
      channelId: "project",
      content: "Deadline gửi bản demo là 17:00 thứ Sáu, mình đang hoàn thành slide."
    },
    {
      delay: 1400,
      userId: "user-1",
      channelId: "general",
      content: "Chốt dùng magic link cho bản demo. @Bạn kiểm tra giúp luồng onboarding nha."
    },
    {
      delay: 1200,
      userId: "user-3",
      channelId: "random",
      content: "Sau khi chốt demo chúng ta đi ăn mừng nhé 🎉"
    }
  ];

  let configuration = null;
  let messageTimer = null;
  let typingTimer = null;

  function clearTimers() {
    window.clearTimeout(messageTimer);
    window.clearTimeout(typingTimer);
    messageTimer = null;
    typingTimer = null;
  }

  function scheduleNext() {
    if (!configuration || !configuration.isRunning()) return;
    const index = configuration.getIndex();
    if (index >= scenario.length) {
      configuration.onStatus("complete");
      return;
    }

    const step = scenario[index];
    typingTimer = window.setTimeout(() => {
      if (configuration?.isRunning()) configuration.onTyping(step.userId);
    }, Math.min(350, step.delay / 2));

    messageTimer = window.setTimeout(() => {
      if (!configuration?.isRunning()) return;
      configuration.onTyping(null);
      configuration.onMessage(step, index);
      configuration.setIndex(index + 1);
      scheduleNext();
    }, step.delay);
  }

  function configure(options) {
    configuration = options;
  }

  function start() {
    if (!configuration || configuration.isRunning()) return;
    configuration.onStatus("running");
    scheduleNext();
  }

  function pause() {
    clearTimers();
    if (configuration) {
      configuration.onTyping(null);
      configuration.onStatus("paused");
    }
  }

  function restart() {
    clearTimers();
    if (!configuration) return;
    configuration.setIndex(0);
    configuration.onTyping(null);
    configuration.onStatus("running");
    scheduleNext();
  }

  window.DiscordSimulator = {
    scenario,
    configure,
    start,
    pause,
    restart
  };
})();
