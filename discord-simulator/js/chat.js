(function () {
  "use strict";

  function escapeHTML(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("vi-VN", {
      hour: "2-digit",
      minute: "2-digit"
    }).format(date);
  }

  function formatFullDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("vi-VN", {
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    }).format(date);
  }

  function getChannelMessages(state, channelId) {
    return state.messages.filter((message) => message.channelId === channelId);
  }

  function getReadRecord(state, userId, channelId) {
    return state.readState?.[userId]?.[channelId] || { lastReadMessageId: null };
  }

  function getLastReadIndex(state, userId, channelId) {
    const messages = getChannelMessages(state, channelId);
    const lastReadId = getReadRecord(state, userId, channelId).lastReadMessageId;
    if (!lastReadId) return -1;
    return messages.findIndex((message) => message.id === lastReadId);
  }

  function getUnreadMessages(state, userId, channelId, excludedMessageId) {
    const messages = getChannelMessages(state, channelId);
    const lastReadIndex = getLastReadIndex(state, userId, channelId);
    return messages.slice(lastReadIndex + 1).filter((message) => {
      return message.id !== excludedMessageId && message.authorId !== userId;
    });
  }

  function getUnreadCount(state, userId, channelId) {
    return getUnreadMessages(state, userId, channelId).filter((message) => {
      const author = state.users.find((user) => user.id === message.authorId);
      return !author?.isBot;
    }).length;
  }

  function createMessage({ channelId, authorId, content, mentions, replyTo, idPrefix }) {
    const randomPart = Math.random().toString(36).slice(2, 8);
    return {
      id: `${idPrefix || "message"}-${Date.now()}-${randomPart}`,
      channelId,
      authorId,
      content,
      createdAt: new Date().toISOString(),
      mentions: mentions || [],
      replyTo: replyTo || null
    };
  }

  function normalizeOutgoingContent(rawContent) {
    const normalizedContent = String(rawContent).trim();
    if (!normalizedContent) return "";
    if (/^\/bot(?:\s|$)/iu.test(normalizedContent)) {
      return normalizedContent.replace(/^\/bot(?:\s+|$)/iu, "@SummaryBot ").trim();
    }
    return normalizedContent;
  }

  function parseMentions(content, users) {
    const lower = content.toLocaleLowerCase("vi");
    return users
      .filter((user) => lower.includes(`@${user.name.toLocaleLowerCase("vi")}`))
      .map((user) => user.id);
  }

  function renderContent(content) {
    const escapedContent = escapeHTML(content);
    return escapedContent
      .replace(
        /(https?:\/\/[^\s<]+)/giu,
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
      )
      .replace(/(@[\p{L}\p{N}_-]+)/gu, '<span class="mention">$1</span>')
      .replace(/\n/g, "<br>");
  }

  window.DiscordChat = {
    escapeHTML,
    formatTime,
    formatFullDate,
    getChannelMessages,
    getLastReadIndex,
    getUnreadMessages,
    getUnreadCount,
    createMessage,
    normalizeOutgoingContent,
    parseMentions,
    renderContent
  };
})();
