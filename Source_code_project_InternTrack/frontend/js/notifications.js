import { apiRequest } from "./api.js";

let pollTimer = 0;
let dropdownOpen = false;

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function setOpen(container, open) {
  dropdownOpen = open;
  const button = container.querySelector("[data-notification-toggle]");
  const dropdown = container.querySelector("[data-notification-dropdown]");
  if (dropdown instanceof HTMLElement) dropdown.hidden = !open;
  button?.setAttribute("aria-expanded", String(open));
}

async function loadNotifications(container) {
  const badge = container.querySelector("[data-notification-count]");
  const list = container.querySelector("[data-notification-list]");
  try {
    const [unread, all] = await Promise.all([
      apiRequest("notifications/unread"),
      apiRequest("notifications"),
    ]);
    const unreadCount = Array.isArray(unread) ? unread.length : 0;
    if (badge instanceof HTMLElement) {
      badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
      badge.hidden = unreadCount === 0;
    }
    if (!(list instanceof HTMLElement)) return;
    if (!Array.isArray(all) || !all.length) {
      list.innerHTML = '<p class="notification-empty">Chưa có thông báo.</p>';
      return;
    }
    list.innerHTML = all.slice(0, 20).map((item) => `
      <button class="notification-item ${item.is_read ? "" : "is-unread"}" type="button"
        data-notification-id="${item.id}" ${item.is_read ? "disabled" : ""}>
        <span class="notification-item-copy">
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.content)}</span>
          <time>${escapeHtml(formatDate(item.created_at))}</time>
        </span>
        ${item.is_read ? "" : '<span class="notification-unread-dot" aria-label="Chưa đọc"></span>'}
      </button>
    `).join("");
  } catch (error) {
    if (badge instanceof HTMLElement) badge.hidden = true;
    if (list instanceof HTMLElement) {
      list.innerHTML = `<p class="notification-empty notification-error">${escapeHtml(error.message)}</p>`;
    }
  }
}

export async function initializeNotifications() {
  let topbar = document.querySelector(".topbar");
  if (!(topbar instanceof HTMLElement)) {
    topbar = document.createElement("header");
    topbar.className = "topbar notification-fallback-topbar";
    topbar.innerHTML = '<span class="topbar-spacer"></span>';
    document.body.insertBefore(topbar, document.body.firstChild);
  }
  let container = topbar.querySelector("[data-notification-menu]");
  if (!container) {
    container = document.createElement("div");
    container.className = "notification-menu";
    container.dataset.notificationMenu = "";
    container.innerHTML = `
      <button class="notification-button" type="button" data-notification-toggle
        aria-haspopup="dialog" aria-expanded="false" aria-label="Thông báo">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path>
          <path d="M10 21h4"></path>
        </svg>
        <span class="notification-dot" data-notification-count hidden>0</span>
      </button>
      <div class="notification-dropdown" data-notification-dropdown role="dialog"
        aria-label="Danh sách thông báo" hidden>
        <div class="notification-heading">
          <strong>Thông báo</strong>
          <button type="button" data-notification-read-all>Đánh dấu tất cả đã đọc</button>
        </div>
        <div class="notification-list" data-notification-list>
          <p class="notification-empty">Đang tải thông báo...</p>
        </div>
      </div>
    `;
    const account = topbar.querySelector(".account-menu-container");
    if (account) topbar.insertBefore(container, account);
    else topbar.append(container);
  }

  container.querySelector("[data-notification-toggle]")?.addEventListener("click", () => {
    setOpen(container, !dropdownOpen);
  });
  container.querySelector("[data-notification-read-all]")?.addEventListener("click", () => {
    void apiRequest("notifications/read-all", { method: "PATCH" })
      .then(() => loadNotifications(container))
      .catch((error) => console.error(error));
  });
  container.querySelector("[data-notification-list]")?.addEventListener("click", (event) => {
    const item = event.target instanceof Element
      ? event.target.closest("[data-notification-id]")
      : null;
    if (!(item instanceof HTMLElement)) return;
    void apiRequest(`notifications/${item.dataset.notificationId}/read`, { method: "PATCH" })
      .then(() => loadNotifications(container))
      .catch((error) => console.error(error));
  });
  document.addEventListener("click", (event) => {
    if (event.target instanceof Node && !container.contains(event.target)) {
      setOpen(container, false);
    }
  });

  await loadNotifications(container);
  if (pollTimer) window.clearInterval(pollTimer);
  pollTimer = window.setInterval(() => void loadNotifications(container), 60000);
}