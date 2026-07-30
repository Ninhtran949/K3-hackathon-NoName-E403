(function () {
  "use strict";

  const topicKeywords = {
    meeting: ["họp", "meeting", "trao đổi", "15:00", "15 giờ", "16 giờ", "lịch"],
    deadline: ["deadline", "hạn", "thứ sáu", "ngày mai", "trước"],
    task: ["phụ trách", "hoàn thành", "làm", "kiểm tra", "chuẩn bị", "nhớ"],
    issue: ["lỗi", "bug", "không hoạt động", "401", "500", "vấn đề", "kẹt"],
    decision: ["thống nhất", "quyết định", "chốt", "sẽ dùng", "ưu tiên"],
    document: ["tài liệu", "file", "link", "thiết kế", "slide", "bảng"]
  };

  function normalize(text) {
    return String(text)
      .toLocaleLowerCase("vi")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d");
  }

  function includesAny(text, terms) {
    const normalizedText = normalize(text);
    return terms.some((term) => normalizedText.includes(normalize(term)));
  }

  function detectIntent(question) {
    const text = normalize(question);
    if (
      ["huong dan", "tai lieu", "cach lam", "cach cai", "link", "duong dan", "docs"].some(
        (term) => text.includes(term)
      )
    ) {
      return "guides";
    }
    if (["tom tat", "bo lo", "tin gi moi", "co gi moi"].some((term) => text.includes(term))) {
      return "summary";
    }
    if (text.includes("thong nhat") || text.includes("quyet dinh") || text.includes("chot")) {
      return "decisions";
    }
    if (text.includes("van de") || text.includes("loi") || text.includes("bug")) {
      return "issues";
    }
    if (text.includes("ai") && (text.includes("hop") || text.includes("cuoc hop"))) {
      return "meeting_author";
    }
    return "unknown";
  }

  function removeBotMention(content) {
    return String(content).replace(/@SummaryBot/giu, "").trim();
  }

  function getAuthor(message, users) {
    return users.find((user) => user.id === message.authorId);
  }

  function usefulMessages(messages, users) {
    return messages.filter((message) => {
      const author = getAuthor(message, users);
      return author && !author.isBot && author.id !== "current-user";
    });
  }

  function groupByTopic(messages) {
    const groups = {};
    Object.entries(topicKeywords).forEach(([topic, keywords]) => {
      groups[topic] = messages.filter((message) => includesAny(message.content, keywords));
    });
    return groups;
  }

  function compactContent(content, maxLength) {
    const cleaned = String(content).replace(/\s+/g, " ").trim();
    if (cleaned.length <= maxLength) return cleaned;
    return `${cleaned.slice(0, maxLength - 1).trim()}…`;
  }

  function uniqueByContent(messages) {
    const seen = new Set();
    return messages.filter((message) => {
      const key = normalize(message.content);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function lineFor(message, users) {
    const author = getAuthor(message, users);
    return `• ${author?.name || "Một thành viên"}: ${compactContent(message.content, 135)}`;
  }

  function extractLinks(content) {
    const matches = String(content).match(/https?:\/\/[^\s]+/giu) || [];
    return matches.map((url) => url.replace(/[),.!?;:]+$/u, ""));
  }

  function commentWithoutLinks(content) {
    return String(content)
      .replace(/https?:\/\/[^\s]+/giu, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[:\-–]\s*$/u, "");
  }

  function generateGuideAnswer(messages, users) {
    const linkedMessages = uniqueByContent(messages)
      .map((message) => ({ message, links: extractLinks(message.content) }))
      .filter((item) => item.links.length)
      .slice(0, 5);

    if (!linkedMessages.length) {
      return "Mình chưa tìm thấy bình luận nào có kèm link hướng dẫn trong kênh này.";
    }

    const lines = [
      `Mình tìm thấy ${linkedMessages.length} hướng dẫn có liên quan trong kênh này:`
    ];

    linkedMessages.forEach(({ message, links }, index) => {
      const author = getAuthor(message, users);
      const comment = commentWithoutLinks(message.content);
      lines.push(
        "",
        `Hướng dẫn ${index + 1} · Bình luận của ${author?.name || "một thành viên"}:`,
        `“${compactContent(comment, 220)}”`,
        "Link:",
        ...links
      );
    });

    return lines.join("\n");
  }

  function generateSummary(messages, users) {
    const participants = new Set(messages.map((message) => message.authorId));
    const groups = groupByTopic(messages);
    const priority = [
      ...groups.decision,
      ...groups.meeting,
      ...groups.deadline,
      ...groups.task,
      ...groups.document
    ];
    const highlights = uniqueByContent(priority).slice(0, 5);
    const fallback = uniqueByContent(messages).slice(0, 4);
    const issues = uniqueByContent(groups.issue).slice(0, 3);
    const selected = highlights.length ? highlights : fallback;

    const lines = [
      `Bạn đã bỏ lỡ ${messages.length} tin nhắn từ ${participants.size} thành viên.`,
      "",
      "Tóm tắt:",
      ...selected.map((message) => lineFor(message, users))
    ];

    if (issues.length) {
      lines.push("", "Nội dung cần chú ý:", ...issues.map((message) => lineFor(message, users)));
    }
    return lines.join("\n");
  }

  function generateBotAnswer(question, unreadMessages, users) {
    const messages = usefulMessages(unreadMessages, users);
    const intent = detectIntent(question);

    if (intent === "guides") {
      return generateGuideAnswer(messages, users);
    }

    if (!messages.length) {
      return "Bạn không bỏ lỡ tin nhắn nào trong kênh này. Mọi thứ đã được cập nhật rồi ✨";
    }

    const groups = groupByTopic(messages);

    if (intent === "summary") {
      return generateSummary(messages, users);
    }

    if (intent === "decisions") {
      if (!groups.decision.length) {
        return "Mình chưa tìm thấy quyết định hoặc nội dung đã thống nhất trong phần tin nhắn bạn bỏ lỡ.";
      }
      return ["Các quyết định mình tìm thấy:", ...uniqueByContent(groups.decision).map((message) => lineFor(message, users))].join("\n");
    }

    if (intent === "issues") {
      if (!groups.issue.length) {
        return "Mình chưa phát hiện vấn đề hoặc lỗi nào trong phần tin nhắn bạn bỏ lỡ.";
      }
      return ["Các vấn đề đang được thảo luận:", ...uniqueByContent(groups.issue).map((message) => lineFor(message, users))].join("\n");
    }

    if (intent === "meeting_author") {
      if (!groups.meeting.length) {
        return "Không có ai nhắc đến cuộc họp trong phần tin nhắn bạn bỏ lỡ.";
      }
      const names = [...new Set(groups.meeting.map((message) => getAuthor(message, users)?.name).filter(Boolean))];
      return `${names.join(", ")} đã nhắc đến cuộc họp.\n\n${groups.meeting.map((message) => lineFor(message, users)).join("\n")}`;
    }

    return [
      "Mình chưa hiểu rõ câu hỏi. Bạn có thể yêu cầu:",
      "• Tóm tắt những tin nhắn chưa đọc",
      "• Liệt kê các quyết định",
      "• Liệt kê vấn đề đang được thảo luận",
      "• Tìm người đã nhắc đến cuộc họp",
      "• Tìm bình luận có kèm link hướng dẫn"
    ].join("\n");
  }

  window.DiscordBot = {
    detectIntent,
    removeBotMention,
    extractLinks,
    generateBotAnswer
  };
})();
