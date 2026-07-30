(function () {
  "use strict";

  const STORAGE_KEY = "discordSimulatorState.v1";
  const Chat = window.DiscordChat;
  const Bot = window.DiscordBot;
  const Data = window.DiscordSimulatorData;
  const Simulator = window.DiscordSimulator;

  let appState = loadState();
  let botReplyTimer = null;
  let toastTimer = null;

  const elements = {};

  function cacheElements() {
    [
      "appShell",
      "channelSidebar",
      "channelList",
      "totalUnread",
      "simulatorIndicator",
      "currentUserPanel",
      "activeChannelName",
      "activeChannelDescription",
      "presencePill",
      "awayBanner",
      "messageArea",
      "messageList",
      "newMessagePill",
      "newMessageCount",
      "typingRow",
      "replyPreview",
      "replyText",
      "messageForm",
      "messageInput",
      "mentionMenu",
      "commandMenu",
      "emojiPopover",
      "memberSidebar",
      "memberList",
      "mobileScrim",
      "toastRegion"
    ].forEach((id) => {
      elements[id] = document.getElementById(id);
    });
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!saved || !Array.isArray(saved.users) || !Array.isArray(saved.channels) || !Array.isArray(saved.messages)) {
        return Data.createInitialState();
      }
      const baseline = Data.createInitialState();
      if (saved.dataVersion !== baseline.dataVersion) {
        return baseline;
      }
      return {
        ...baseline,
        ...saved,
        simulatorRunning: false,
        botTyping: false,
        typingUserId: null
      };
    } catch (error) {
      console.warn("Không thể đọc trạng thái đã lưu:", error);
      return Data.createInitialState();
    }
  }

  function saveState() {
    try {
      const stateToSave = {
        ...appState,
        simulatorRunning: false,
        botTyping: false,
        typingUserId: null
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
    } catch (error) {
      console.warn("Không thể lưu trạng thái:", error);
    }
  }

  function getUser(userId) {
    return appState.users.find((user) => user.id === userId);
  }

  function getChannel(channelId) {
    return appState.channels.find((channel) => channel.id === channelId);
  }

  function avatarHTML(user, small) {
    const safeUser = user || { name: "Ẩn danh", initials: "?", color: "#687080", status: "offline" };
    const classes = ["avatar", small ? "avatar--small" : "", safeUser.isBot ? "avatar--bot" : ""]
      .filter(Boolean)
      .join(" ");
    return `
      <div class="${classes}" style="--avatar-color:${safeUser.color}" aria-label="${Chat.escapeHTML(safeUser.name)}">
        ${Chat.escapeHTML(safeUser.initials)}
        <span class="status-dot ${safeUser.status}"></span>
      </div>
    `;
  }

  function renderChannels() {
    elements.channelList.innerHTML = `
      <div class="section-label"><span>Kênh văn bản</span></div>
      ${appState.channels
        .map((channel) => {
          const unread = Chat.getUnreadCount(appState, appState.currentUserId, channel.id);
          const classes = [
            "channel-item",
            appState.activeChannelId === channel.id ? "is-active" : "",
            unread ? "has-unread" : ""
          ]
            .filter(Boolean)
            .join(" ");
          return `
            <button class="${classes}" type="button" data-channel-id="${channel.id}">
              <span class="channel-item__hash">#</span>
              <span class="channel-item__name">${Chat.escapeHTML(channel.name)}</span>
              ${unread ? `<span class="unread-badge">${unread > 99 ? "99+" : unread}</span>` : ""}
            </button>
          `;
        })
        .join("")}
    `;

    const total = appState.channels.reduce(
      (sum, channel) => sum + Chat.getUnreadCount(appState, appState.currentUserId, channel.id),
      0
    );
    elements.totalUnread.textContent = `${total} tin chưa đọc`;
  }

  function renderHeader() {
    const channel = getChannel(appState.activeChannelId);
    elements.activeChannelName.textContent = channel?.name || "general";
    elements.activeChannelDescription.textContent = channel?.description || "";
    elements.messageInput.placeholder = `Nhắn tin tới #${channel?.name || "general"}`;
    elements.awayBanner.hidden = !appState.userAway;
    elements.presencePill.classList.toggle("is-away", appState.userAway);
    elements.presencePill.innerHTML = appState.userAway
      ? "<i></i> Đang rời kênh"
      : "<i></i> Đang trực tuyến";
  }

  function renderMessages(options) {
    const settings = { scroll: false, ...options };
    const channel = getChannel(appState.activeChannelId);
    const messages = Chat.getChannelMessages(appState, appState.activeChannelId);
    const lastReadIndex = Chat.getLastReadIndex(appState, appState.currentUserId, appState.activeChannelId);
    const firstUnreadIndex = messages.findIndex(
      (message, index) => index > lastReadIndex && message.authorId !== appState.currentUserId && !getUser(message.authorId)?.isBot
    );
    let previousMessage = null;

    const html = [
      `<div class="channel-intro">
        <div class="channel-intro__icon">#</div>
        <h1>Chào mừng đến với #${Chat.escapeHTML(channel?.name || "")}!</h1>
        <p>${Chat.escapeHTML(channel?.description || "")}. Đây là điểm bắt đầu của kênh.</p>
      </div>`
    ];

    messages.forEach((message, index) => {
      if (index === firstUnreadIndex) {
        html.push('<div class="unread-divider" id="unreadDivider">Tin nhắn mới</div>');
      }

      const author = getUser(message.authorId);
      const replyMessage = message.replyTo ? appState.messages.find((item) => item.id === message.replyTo) : null;
      const replyAuthor = replyMessage ? getUser(replyMessage.authorId) : null;
      const createdAt = new Date(message.createdAt);
      const previousAt = previousMessage ? new Date(previousMessage.createdAt) : null;
      const grouped =
        previousMessage &&
        previousMessage.authorId === message.authorId &&
        createdAt - previousAt < 5 * 60 * 1000 &&
        !message.replyTo;
      const mentioned = message.mentions?.includes(appState.currentUserId);
      const classes = [
        "message",
        grouped ? "is-grouped" : "",
        author?.isBot ? "is-bot" : "",
        author?.id === appState.currentUserId ? "is-current" : "",
        mentioned ? "is-mentioned" : ""
      ]
        .filter(Boolean)
        .join(" ");

      html.push(`
        <article class="${classes}" data-message-id="${message.id}">
          <div class="message__avatar">${avatarHTML(author)}</div>
          <div class="message__body">
            ${
              replyMessage
                ? `<div class="message__reply">
                    <strong>${Chat.escapeHTML(replyAuthor?.name || "Ẩn danh")}</strong>
                    <span>${Chat.escapeHTML(replyMessage.content.slice(0, 80))}</span>
                  </div>`
                : ""
            }
            <div class="message__header">
              <span class="message__author" style="--author-color:${author?.color || "#fff"}">${Chat.escapeHTML(author?.name || "Ẩn danh")}</span>
              ${author?.isBot ? '<span class="bot-tag">APP</span>' : ""}
              <time class="message__time" datetime="${Chat.escapeHTML(message.createdAt)}" title="${Chat.escapeHTML(Chat.formatFullDate(message.createdAt))}">
                Hôm nay lúc ${Chat.formatTime(message.createdAt)}
              </time>
            </div>
            <div class="message__content">${Chat.renderContent(message.content)}</div>
          </div>
          <div class="message-actions" aria-label="Thao tác tin nhắn">
            <button type="button" data-reaction-message="${message.id}" title="Thả cảm xúc">☺</button>
            <button type="button" data-reply-message="${message.id}" title="Trả lời">↩</button>
          </div>
        </article>
      `);
      previousMessage = message;
    });

    elements.messageList.innerHTML = html.join("");

    const unreadCount = Chat.getUnreadCount(appState, appState.currentUserId, appState.activeChannelId);
    elements.newMessagePill.hidden = unreadCount === 0;
    elements.newMessageCount.textContent = `${unreadCount} tin mới`;

    if (settings.scroll === "bottom") {
      requestAnimationFrame(() => {
        elements.messageList.scrollTop = elements.messageList.scrollHeight;
      });
    } else if (settings.scroll === "unread") {
      requestAnimationFrame(() => {
        document.getElementById("unreadDivider")?.scrollIntoView({ block: "center" });
      });
    }
  }

  function renderMembers() {
    const groups = [
      {
        label: "Trực tuyến",
        users: appState.users.filter((user) => user.status !== "offline")
      },
      {
        label: "Ngoại tuyến",
        users: appState.users.filter((user) => user.status === "offline")
      }
    ];

    elements.memberList.innerHTML = groups
      .map(
        (group) => `
          <section class="member-group">
            <div class="member-group__title">${group.label} — ${group.users.length}</div>
            ${group.users
              .map(
                (user) => `
                  <div class="member-item ${user.status === "offline" ? "is-offline" : ""}">
                    ${avatarHTML(user, true)}
                    <div class="member-item__info">
                      <div class="member-item__name">
                        <span style="color:${user.color}">${Chat.escapeHTML(user.name)}</span>
                        ${user.isBot ? '<span class="bot-tag">BOT</span>' : ""}
                      </div>
                      <div class="member-item__activity">${Chat.escapeHTML(user.activity)}</div>
                    </div>
                  </div>
                `
              )
              .join("")}
          </section>
        `
      )
      .join("");
  }

  function renderCurrentUser() {
    const currentUser = getUser(appState.currentUserId);
    elements.currentUserPanel.innerHTML = `
      ${avatarHTML(currentUser, true)}
      <div class="current-user__info">
        <strong>${Chat.escapeHTML(currentUser?.name || "Bạn")}</strong>
        <span>${appState.userAway ? "Đang rời kênh" : "Sẵn sàng trò chuyện"}</span>
      </div>
      <div class="current-user__actions">
        <button type="button" aria-label="Tắt mic">♩</button>
        <button type="button" data-action="reset-data" aria-label="Đặt lại dữ liệu" title="Đặt lại dữ liệu">⚙</button>
      </div>
    `;
  }

  function renderTyping() {
    const typingUsers = [];
    if (appState.typingUserId) typingUsers.push(getUser(appState.typingUserId)?.name);
    if (appState.botTyping) typingUsers.push("SummaryBot");
    const names = typingUsers.filter(Boolean);
    if (!names.length) {
      elements.typingRow.innerHTML = "";
      return;
    }
    elements.typingRow.innerHTML = `
      <span class="typing-dots"><i></i><i></i><i></i></span>
      <strong>${Chat.escapeHTML(names.join(" và "))}</strong> đang nhập...
    `;
  }

  function renderSimulatorState() {
    elements.simulatorIndicator.classList.toggle("is-live", appState.simulatorRunning);
    elements.simulatorIndicator.textContent = appState.simulatorRunning
      ? "Đang chạy"
      : appState.simulatorIndex >= Simulator.scenario.length
        ? "Đã hoàn tất"
        : "Tạm dừng";
  }

  function renderReply() {
    const message = appState.replyingTo
      ? appState.messages.find((item) => item.id === appState.replyingTo)
      : null;
    if (!message) {
      elements.replyPreview.hidden = true;
      return;
    }
    const author = getUser(message.authorId);
    elements.replyText.innerHTML = `Đang trả lời <strong>${Chat.escapeHTML(author?.name || "Ẩn danh")}</strong>`;
    elements.replyPreview.hidden = false;
  }

  function renderApp(options) {
    renderChannels();
    renderHeader();
    renderMessages(options);
    renderMembers();
    renderCurrentUser();
    renderTyping();
    renderSimulatorState();
    renderReply();
  }

  function showToast(message) {
    window.clearTimeout(toastTimer);
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    elements.toastRegion.replaceChildren(toast);
    toastTimer = window.setTimeout(() => toast.remove(), 3000);
  }

  function switchChannel(channelId) {
    if (!getChannel(channelId)) return;
    appState.activeChannelId = channelId;
    appState.replyingTo = null;
    saveState();
    closeOverlays();
    renderApp({ scroll: Chat.getUnreadCount(appState, appState.currentUserId, channelId) ? "unread" : "bottom" });
  }

  function ensureReadRecord(channelId) {
    appState.readState[appState.currentUserId] ||= {};
    appState.readState[appState.currentUserId][channelId] ||= { lastReadMessageId: null };
    return appState.readState[appState.currentUserId][channelId];
  }

  function markChannelRead(channelId, silent) {
    const messages = Chat.getChannelMessages(appState, channelId);
    const lastMessage = messages.at(-1);
    ensureReadRecord(channelId).lastReadMessageId = lastMessage?.id || null;
    saveState();
    renderApp({ scroll: channelId === appState.activeChannelId ? "bottom" : false });
    if (!silent) showToast("Đã đánh dấu kênh là đã đọc.");
  }

  function markAllRead() {
    appState.channels.forEach((channel) => {
      const messages = Chat.getChannelMessages(appState, channel.id);
      ensureReadRecord(channel.id).lastReadMessageId = messages.at(-1)?.id || null;
    });
    saveState();
    renderApp();
    showToast("Đã đánh dấu tất cả tin nhắn là đã đọc.");
  }

  function resizeComposer() {
    elements.messageInput.style.height = "auto";
    elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 130)}px`;
  }

  function updateComposerMenus() {
    const beforeCursor = elements.messageInput.value.slice(0, elements.messageInput.selectionStart);
    const mentionQuery = beforeCursor.match(/(?:^|\s)@([^\s@]*)$/u);
    const query = mentionQuery?.[1]?.toLocaleLowerCase("vi") || "";
    const shouldShow = Boolean(mentionQuery) && "summarybot".startsWith(query);
    elements.mentionMenu.hidden = !shouldShow;

    const commandQuery = elements.messageInput.value.trimStart();
    const shouldShowCommand =
      /^\/[a-z]*$/iu.test(commandQuery) &&
      "/bot".startsWith(commandQuery.toLocaleLowerCase("vi"));
    elements.commandMenu.hidden = !shouldShowCommand || shouldShow;
  }

  function insertMention(name) {
    const input = elements.messageInput;
    const cursor = input.selectionStart;
    const beforeCursor = input.value.slice(0, cursor);
    const match = beforeCursor.match(/(?:^|\s)@[^\s@]*$/u);
    if (match) {
      const mentionStart = beforeCursor.lastIndexOf("@");
      input.value = `${input.value.slice(0, mentionStart)}@${name} ${input.value.slice(cursor)}`;
      const nextPosition = mentionStart + name.length + 2;
      input.setSelectionRange(nextPosition, nextPosition);
    } else {
      insertAtCursor(`@${name} `);
    }
    elements.mentionMenu.hidden = true;
    input.focus();
    resizeComposer();
  }

  function insertBotCommand() {
    elements.messageInput.value = "/bot ";
    elements.messageInput.setSelectionRange(5, 5);
    elements.commandMenu.hidden = true;
    elements.mentionMenu.hidden = true;
    elements.messageInput.focus();
    resizeComposer();
  }

  function insertAtCursor(text) {
    const input = elements.messageInput;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const prefix = start > 0 && !/\s/.test(input.value[start - 1]) ? " " : "";
    input.value = `${input.value.slice(0, start)}${prefix}${text}${input.value.slice(end)}`;
    const nextPosition = start + prefix.length + text.length;
    input.setSelectionRange(nextPosition, nextPosition);
    input.focus();
    resizeComposer();
  }

  function sendMessage(rawContent) {
    const content = Chat.normalizeOutgoingContent(rawContent);
    if (!content) return;
    const mentions = Chat.parseMentions(content, appState.users);
    const message = Chat.createMessage({
      authorId: appState.currentUserId,
      channelId: appState.activeChannelId,
      content,
      mentions,
      replyTo: appState.replyingTo
    });
    appState.messages.push(message);
    appState.replyingTo = null;
    elements.messageInput.value = "";
    elements.commandMenu.hidden = true;
    elements.mentionMenu.hidden = true;
    resizeComposer();
    saveState();
    renderApp({ scroll: "bottom" });

    if (mentions.includes("bot-1") || /@SummaryBot/iu.test(content)) {
      handleBotMention(message);
    }
  }

  function handleBotMention(userMessage) {
    window.clearTimeout(botReplyTimer);
    const question = Bot.removeBotMention(userMessage.content);
    const intent = Bot.detectIntent(question);
    const sourceMessages =
      intent === "guides"
        ? Chat.getChannelMessages(appState, userMessage.channelId).filter(
            (message) => message.id !== userMessage.id
          )
        : Chat.getUnreadMessages(
            appState,
            userMessage.authorId,
            userMessage.channelId,
            userMessage.id
          );
    appState.botTyping = true;
    renderTyping();

    botReplyTimer = window.setTimeout(() => {
      const answer = Bot.generateBotAnswer(question, sourceMessages, appState.users);
      const botMessage = Chat.createMessage({
        authorId: "bot-1",
        channelId: userMessage.channelId,
        content: answer,
        mentions: [],
        idPrefix: "bot"
      });
      appState.botTyping = false;
      appState.messages.push(botMessage);
      saveState();
      renderApp({ scroll: appState.activeChannelId === userMessage.channelId ? "bottom" : false });
    }, 1050);
  }

  function receiveSimulatedMessage(step, index) {
    const mentions = Chat.parseMentions(step.content, appState.users);
    const message = Chat.createMessage({
      authorId: step.userId,
      channelId: step.channelId,
      content: step.content,
      mentions,
      idPrefix: `sim-${index}`
    });
    appState.messages.push(message);

    const atBottom =
      elements.messageList.scrollHeight - elements.messageList.scrollTop - elements.messageList.clientHeight < 90;
    const canMarkRead =
      !appState.userAway &&
      step.channelId === appState.activeChannelId &&
      document.visibilityState === "visible" &&
      atBottom;

    if (canMarkRead) {
      ensureReadRecord(step.channelId).lastReadMessageId = message.id;
    }
    saveState();
    renderApp({ scroll: step.channelId === appState.activeChannelId && canMarkRead ? "bottom" : false });
  }

  function toggleAway() {
    appState.userAway = !appState.userAway;
    saveState();
    renderApp();
    showToast(
      appState.userAway
        ? "Bạn đã rời kênh. Tin nhắn mới sẽ được giữ là chưa đọc."
        : "Chào mừng quay lại! Hãy hỏi SummaryBot về phần đã bỏ lỡ."
    );
  }

  function resetData() {
    Simulator.pause();
    window.clearTimeout(botReplyTimer);
    appState = Data.createInitialState();
    localStorage.removeItem(STORAGE_KEY);
    renderApp({ scroll: "unread" });
    showToast("Dữ liệu mẫu đã được khôi phục.");
  }

  function closeOverlays() {
    elements.appShell.classList.remove("sidebar-open", "members-open");
  }

  function scrollToUnread() {
    const divider = document.getElementById("unreadDivider");
    if (divider) {
      divider.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      elements.messageList.scrollTo({ top: elements.messageList.scrollHeight, behavior: "smooth" });
    }
  }

  function handleAction(action) {
    switch (action) {
      case "mark-all":
        markAllRead();
        break;
      case "mark-channel":
        markChannelRead(appState.activeChannelId);
        break;
      case "sim-start":
        Simulator.start();
        break;
      case "sim-pause":
        Simulator.pause();
        break;
      case "sim-restart":
        Simulator.restart();
        showToast("Kịch bản mô phỏng đã chạy lại từ đầu.");
        break;
      case "toggle-away":
        toggleAway();
        break;
      case "toggle-sidebar":
        elements.appShell.classList.toggle("sidebar-open");
        elements.appShell.classList.remove("members-open");
        break;
      case "toggle-members":
        elements.appShell.classList.toggle("members-open");
        elements.appShell.classList.remove("sidebar-open");
        break;
      case "close-overlays":
        closeOverlays();
        break;
      case "scroll-unread":
        scrollToUnread();
        break;
      case "mention-bot":
        insertAtCursor("@SummaryBot ");
        break;
      case "toggle-emoji":
        elements.emojiPopover.hidden = !elements.emojiPopover.hidden;
        break;
      case "cancel-reply":
        appState.replyingTo = null;
        renderReply();
        break;
      case "attachment":
        showToast("Bản mô phỏng chưa tải tệp lên máy chủ.");
        break;
      case "reset-data":
        resetData();
        break;
      default:
        break;
    }
  }

  function bindEvents() {
    elements.messageForm.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage(elements.messageInput.value);
    });

    elements.messageInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !elements.mentionMenu.hidden) {
        elements.mentionMenu.hidden = true;
        return;
      }
      if (event.key === "Escape" && !elements.commandMenu.hidden) {
        elements.commandMenu.hidden = true;
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && !elements.mentionMenu.hidden) {
        event.preventDefault();
        insertMention("SummaryBot");
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && !elements.commandMenu.hidden) {
        event.preventDefault();
        insertBotCommand();
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        sendMessage(elements.messageInput.value);
      }
    });

    elements.messageInput.addEventListener("input", () => {
      resizeComposer();
      updateComposerMenus();
    });

    document.addEventListener("click", (event) => {
      const actionTarget = event.target.closest("[data-action]");
      if (actionTarget) {
        handleAction(actionTarget.dataset.action);
        return;
      }

      const channelTarget = event.target.closest("[data-channel-id]");
      if (channelTarget) {
        switchChannel(channelTarget.dataset.channelId);
        return;
      }

      const commandTarget = event.target.closest("[data-command]");
      if (commandTarget?.dataset.command === "bot") {
        insertBotCommand();
        return;
      }

      const emojiTarget = event.target.closest("[data-emoji]");
      if (emojiTarget) {
        insertAtCursor(emojiTarget.dataset.emoji);
        elements.emojiPopover.hidden = true;
        return;
      }

      const mentionTarget = event.target.closest("[data-mention-user]");
      if (mentionTarget) {
        insertMention(mentionTarget.dataset.mentionUser);
        return;
      }

      const replyTarget = event.target.closest("[data-reply-message]");
      if (replyTarget) {
        appState.replyingTo = replyTarget.dataset.replyMessage;
        renderReply();
        elements.messageInput.focus();
        return;
      }

      const reactionTarget = event.target.closest("[data-reaction-message]");
      if (reactionTarget) {
        insertAtCursor("👍");
        showToast("Emoji đã được thêm vào ô soạn tin.");
      }
    });

    window.addEventListener("beforeunload", saveState);
  }

  function configureSimulator() {
    Simulator.configure({
      getIndex: () => appState.simulatorIndex,
      setIndex: (index) => {
        appState.simulatorIndex = index;
        saveState();
      },
      isRunning: () => appState.simulatorRunning,
      onMessage: receiveSimulatedMessage,
      onTyping: (userId) => {
        appState.typingUserId = userId;
        renderTyping();
      },
      onStatus: (status) => {
        appState.simulatorRunning = status === "running";
        appState.typingUserId = null;
        saveState();
        renderSimulatorState();
        renderTyping();
        if (status === "complete") showToast("Kịch bản mô phỏng đã hoàn tất.");
      }
    });
  }

  function init() {
    cacheElements();
    configureSimulator();
    bindEvents();
    renderApp({ scroll: "unread" });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
