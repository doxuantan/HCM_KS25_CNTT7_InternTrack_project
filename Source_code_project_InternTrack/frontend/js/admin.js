import { ApiError, apiRequest, getAuthSessionPersistence } from "./api.js";
import { logout, requireAuth } from "./auth.js";
import { confirmAction, initializeSharedUi, showToast } from "./ui.js";

const USER_PAGE_SIZE = 100;
const ROLE_LABELS = Object.freeze({
  ADMIN: "Quản trị viên",
  SUPERVISOR: "Giảng viên",
  STUDENT: "Sinh viên",
});
const PERIOD_STATUS_LABELS = Object.freeze({
  UPCOMING: "Sắp diễn ra",
  ACTIVE: "Đang diễn ra",
  COMPLETED: "Đã hoàn thành",
});
const VIEW_LABELS = Object.freeze({
  overview: "Tổng quan",
  users: "Quản lý người dùng",
  supervisors: "Quản lý giảng viên",
  students: "Quản lý sinh viên",
  periods: "Kỳ thực tập",
  teams: "Nhóm thực tập",
  system: "Quản lý hệ thống",
});
const SEARCH_VIEWS = new Set(["users", "supervisors", "students", "periods"]);

const main = document.querySelector("#main-content");
const alertBox = document.querySelector("[data-admin-alert]");
const searchInput = document.querySelector("[data-global-search]");
const searchWrap = document.querySelector("[data-global-search-wrap]");
const userDialog = document.querySelector("[data-user-dialog]");
const userForm = document.querySelector("[data-user-form]");
const detailDialog = document.querySelector("[data-detail-dialog]");
const periodDialog = document.querySelector("[data-period-dialog]");
const periodForm = document.querySelector("[data-period-form]");

let adminUser = null;
let currentView = "overview";
let usersCache = null;
let usersPromise = null;
let periodsCache = null;
let periodsPromise = null;
let alertTimer = 0;

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function getErrorMessage(error) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : "Đã xảy ra lỗi không xác định.";
  }

  if (error.status === 403) {
    return "Tài khoản không có quyền thực hiện thao tác này.";
  }
  if (error.status === 404) {
    return "Không tìm thấy dữ liệu hoặc API tương ứng.";
  }
  if (
    error.status === 422 &&
    (Array.isArray(error.payload?.errors) || Array.isArray(error.payload?.detail))
  ) {
    const validationErrors = error.payload.errors || error.payload.detail;
    const messages = validationErrors
      .map((item) =>
        isRecord(item)
          ? typeof item.message === "string"
            ? item.message
            : typeof item.msg === "string"
              ? item.msg
              : ""
          : "",
      )
      .filter(Boolean);
    return messages.length ? messages.join(" ") : "Dữ liệu gửi lên chưa hợp lệ.";
  }
  if (error.status >= 500) {
    return "Máy chủ gặp sự cố. Vui lòng thử lại sau.";
  }
  if (error.status === 0) {
    return error.message;
  }
  return error.message || "Yêu cầu không thành công.";
}

function showAlert(message, kind = "error") {
  if (kind === "success") {
    showToast(message);
    return;
  }
  if (!(alertBox instanceof HTMLElement)) {
    return;
  }

  window.clearTimeout(alertTimer);
  alertBox.textContent = message;
  alertBox.dataset.kind = kind;
  alertBox.hidden = false;
  if (kind === "success") {
    alertTimer = window.setTimeout(() => {
      alertBox.hidden = true;
    }, 4200);
  }
}

function clearAlert() {
  if (alertBox instanceof HTMLElement) {
    alertBox.hidden = true;
    alertBox.textContent = "";
    delete alertBox.dataset.kind;
  }
}

function setFormMessage(element, message, kind = "error") {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.textContent = message;
  element.dataset.kind = kind;
  element.hidden = !message;
}

function formatDate(value) {
  if (typeof value !== "string" || !value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(date);
}

function formatDateTime(value) {
  if (typeof value !== "string" || !value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(date);
}

function createTextCell(value, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
  return cell;
}

function createStateRow(body, columnCount, message, state = "empty") {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.className = "admin-table-state";
  cell.colSpan = columnCount;
  cell.dataset.state = state;
  cell.setAttribute("role", state === "error" ? "alert" : "status");
  cell.textContent = message;
  row.append(cell);
  body.replaceChildren(row);
  body.setAttribute("aria-busy", String(state === "loading"));
}

function getSearchTerm() {
  return searchInput instanceof HTMLInputElement
    ? searchInput.value.trim().toLocaleLowerCase("vi-VN")
    : "";
}

async function fetchAllUsers() {
  const users = [];
  let skip = 0;

  while (true) {
    const page = await apiRequest(`users?skip=${skip}&limit=${USER_PAGE_SIZE}`);
    if (!Array.isArray(page) || page.some((user) => !isRecord(user))) {
      throw new Error("API người dùng trả về dữ liệu không hợp lệ.");
    }
    users.push(...page);
    if (page.length < USER_PAGE_SIZE) {
      break;
    }
    skip += page.length;
  }

  return users;
}

async function getUsers(force = false) {
  if (force) {
    usersCache = null;
  }
  if (usersCache) {
    return usersCache;
  }
  if (usersPromise) {
    return usersPromise;
  }

  usersPromise = fetchAllUsers();
  try {
    usersCache = await usersPromise;
    return usersCache;
  } finally {
    usersPromise = null;
  }
}

async function getPeriods(force = false) {
  if (force) {
    periodsCache = null;
  }
  if (periodsCache) {
    return periodsCache;
  }
  if (periodsPromise) {
    return periodsPromise;
  }

  periodsPromise = apiRequest("internship-periods").then((periods) => {
    if (!Array.isArray(periods) || periods.some((period) => !isRecord(period))) {
      throw new Error("API kỳ thực tập trả về dữ liệu không hợp lệ.");
    }
    return periods;
  });
  try {
    periodsCache = await periodsPromise;
    return periodsCache;
  } finally {
    periodsPromise = null;
  }
}

function createRoleBadge(role) {
  const badge = document.createElement("span");
  badge.className = "admin-role-badge";
  badge.dataset.role = typeof role === "string" ? role : "";
  badge.textContent = ROLE_LABELS[role] || "Không xác định";
  return badge;
}

function createStatusBadge(isActive) {
  const badge = document.createElement("span");
  badge.className = `admin-status ${isActive ? "admin-status-active" : "admin-status-inactive"}`;
  badge.textContent = isActive ? "Đang hoạt động" : "Đã khóa";
  return badge;
}

function appendActionButton(container, label, action, id, options = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `admin-row-action${options.danger ? " admin-row-action-danger" : ""}`;
  button.dataset.userAction = action;
  button.dataset.userId = String(id);
  button.textContent = label;
  if (options.disabled) {
    button.disabled = true;
    button.title = "Không thể khóa hoặc xóa tài khoản đang đăng nhập.";
  }
  container.append(button);
}

function createUserIdentityCell(user) {
  const cell = document.createElement("td");
  const identity = document.createElement("span");
  identity.className = "admin-user-cell";
  const name = document.createElement("strong");
  name.textContent = typeof user.full_name === "string" ? user.full_name : "—";
  const email = document.createElement("span");
  email.textContent = typeof user.email === "string" ? user.email : "—";
  identity.append(name, email);
  cell.append(identity);
  return cell;
}

function getFilteredUsers(role = "") {
  const term = getSearchTerm();
  const statusFilter =
    currentView === "users"
      ? document.querySelector("[data-user-status-filter]")?.value
      : document.querySelector(
          `[data-view-panel="${currentView}"] [data-people-status-filter]`,
        )?.value;

  return (usersCache || []).filter((user) => {
    if (role && user.role !== role) {
      return false;
    }
    if (statusFilter === "active" && !user.is_active) {
      return false;
    }
    if (statusFilter === "inactive" && user.is_active) {
      return false;
    }
    if (!term) {
      return true;
    }

    const profileText =
      currentView === "students"
        ? `${user.student_profile?.student_code || ""} ${user.student_profile?.class_name || ""} ${user.student_profile?.major || ""}`
        : currentView === "supervisors"
          ? `${user.lecturer_profile?.lecturer_code || ""} ${user.lecturer_profile?.department || ""}`
          : "";
    return `${user.full_name || ""} ${user.email || ""} ${profileText}`
      .toLocaleLowerCase("vi-VN")
      .includes(term);
  });
}

function renderUserTable(body, users, options = {}) {
  const roleFilter = document.querySelector("[data-user-role-filter]")?.value || "";
  const filtered = options.role
    ? getFilteredUsers(options.role)
    : getFilteredUsers(roleFilter);
  if (!filtered.length) {
    createStateRow(
      body,
      options.role ? 5 : 5,
      users.length ? "Không tìm thấy bản ghi phù hợp." : "Chưa có dữ liệu người dùng.",
    );
    return;
  }

  const rows = filtered.map((user) => {
    const row = document.createElement("tr");
    if (options.role === "SUPERVISOR" || options.role === "STUDENT") {
      const profile =
        options.role === "SUPERVISOR" ? user.lecturer_profile : user.student_profile;
      const code = options.role === "SUPERVISOR" ? profile?.lecturer_code : profile?.student_code;
      const description =
        options.role === "SUPERVISOR"
          ? profile?.department
          : [profile?.class_name, profile?.major].filter(Boolean).join(" · ");
      row.append(
        createUserIdentityCell(user),
        createTextCell(code),
        createTextCell(description),
        (() => {
          const cell = document.createElement("td");
          cell.append(createStatusBadge(Boolean(user.is_active)));
          return cell;
        })(),
      );
    } else {
      row.append(
        createUserIdentityCell(user),
        (() => {
          const cell = document.createElement("td");
          cell.append(createRoleBadge(user.role));
          return cell;
        })(),
        (() => {
          const cell = document.createElement("td");
          cell.append(createStatusBadge(Boolean(user.is_active)));
          return cell;
        })(),
        createTextCell(formatDate(user.created_at)),
      );
    }

    const actionCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "admin-row-actions";
    appendActionButton(actions, "Chi tiết", "view", user.id);
    appendActionButton(actions, "Sửa", "edit", user.id);
    if (!options.role) {
      const isCurrentUser = adminUser && Number(user.id) === Number(adminUser.id);
      appendActionButton(
        actions,
        user.is_active ? "Khóa" : "Kích hoạt",
        "status",
        user.id,
        { disabled: isCurrentUser },
      );
      appendActionButton(actions, "Xóa", "delete", user.id, {
        danger: true,
        disabled: isCurrentUser,
      });
    }
    actionCell.append(actions);
    row.append(actionCell);
    return row;
  });

  body.replaceChildren(...rows);
  body.setAttribute("aria-busy", "false");
}

function renderUserViews() {
  const usersBody = document.querySelector("[data-users-rows]");
  const supervisorsBody = document.querySelector("[data-supervisors-rows]");
  const studentsBody = document.querySelector("[data-students-rows]");
  if (!(usersBody instanceof HTMLTableSectionElement)) {
    return;
  }
  renderUserTable(usersBody, usersCache || []);

  if (supervisorsBody instanceof HTMLTableSectionElement) {
    renderUserTable(supervisorsBody, usersCache || [], { role: "SUPERVISOR" });
  }
  if (studentsBody instanceof HTMLTableSectionElement) {
    renderUserTable(studentsBody, usersCache || [], { role: "STUDENT" });
  }

  const count = document.querySelector("[data-users-count]");
  if (count) {
    const visible = getFilteredUsers(document.querySelector("[data-user-role-filter]")?.value || "");
    count.textContent = `Hiển thị ${visible.length} / ${(usersCache || []).length} người dùng.`;
  }
}

function renderRecentUsers(users) {
  const body = document.querySelector("[data-recent-users]");
  if (!(body instanceof HTMLTableSectionElement)) {
    return;
  }
  if (!users.length) {
    createStateRow(body, 4, "Chưa có người dùng để hiển thị.");
    return;
  }

  const recent = [...users]
    .sort((left, right) => (Date.parse(right.created_at || "") || 0) - (Date.parse(left.created_at || "") || 0))
    .slice(0, 5);
  body.replaceChildren(
    ...recent.map((user) => {
      const row = document.createElement("tr");
      row.append(
        createTextCell(user.full_name),
        createTextCell(user.email),
        (() => {
          const cell = document.createElement("td");
          cell.append(createRoleBadge(user.role));
          return cell;
        })(),
        (() => {
          const cell = document.createElement("td");
          cell.append(createStatusBadge(Boolean(user.is_active)));
          return cell;
        })(),
      );
      return row;
    }),
  );
  body.setAttribute("aria-busy", "false");
}

function setStat(name, value, note) {
  const valueElement = document.querySelector(`[data-stat-value="${name}"]`);
  const noteElement = document.querySelector(`[data-stat-note="${name}"]`);
  if (valueElement) {
    valueElement.textContent = value === null ? "—" : String(value);
  }
  if (noteElement) {
    noteElement.textContent = note;
  }
}

async function loadOverview(force = false) {
  const recentBody = document.querySelector("[data-recent-users]");
  if (recentBody instanceof HTMLTableSectionElement) {
    createStateRow(recentBody, 4, "Đang tải dữ liệu...", "loading");
  }
  for (const name of ["users", "admins", "supervisors", "students", "periods"]) {
    setStat(name, null, "Đang tải dữ liệu...");
  }
  setStat("teams", null, "Backend chưa cung cấp API nhóm.");

  const [usersResult, periodsResult] = await Promise.allSettled([
    getUsers(force),
    getPeriods(force),
  ]);
  if (usersResult.status === "fulfilled") {
    const users = usersResult.value;
    setStat("users", users.length, "Tổng số tài khoản trong API người dùng");
    setStat("admins", users.filter((user) => user.role === "ADMIN").length, "Tài khoản role ADMIN");
    setStat(
      "supervisors",
      users.filter((user) => user.role === "SUPERVISOR").length,
      "Tài khoản role SUPERVISOR",
    );
    setStat(
      "students",
      users.filter((user) => user.role === "STUDENT").length,
      "Tài khoản role STUDENT",
    );
    renderRecentUsers(users);
  } else {
    for (const name of ["users", "admins", "supervisors", "students"]) {
      setStat(name, null, "Không tải được API người dùng.");
    }
    if (recentBody instanceof HTMLTableSectionElement) {
      createStateRow(recentBody, 4, getErrorMessage(usersResult.reason), "error");
    }
  }

  if (periodsResult.status === "fulfilled") {
    setStat("periods", periodsResult.value.length, "Số kỳ từ API backend");
  } else {
    setStat("periods", null, "Không tải được API kỳ thực tập.");
  }
}

function renderUserLoadingState() {
  for (const selector of ["[data-users-rows]", "[data-supervisors-rows]", "[data-students-rows]"]) {
    const body = document.querySelector(selector);
    if (body instanceof HTMLTableSectionElement) {
      createStateRow(body, 5, "Đang tải danh sách...", "loading");
    }
  }
}

async function loadUsersView(force = false) {
  renderUserLoadingState();
  await getUsers(force);
  renderUserViews();
}

function renderPeriods() {
  const body = document.querySelector("[data-periods-rows]");
  if (!(body instanceof HTMLTableSectionElement)) {
    return;
  }

  const statusFilter = document.querySelector("[data-period-status-filter]")?.value || "";
  const term = getSearchTerm();
  const periods = (periodsCache || []).filter((period) => {
    if (statusFilter && period.status !== statusFilter) {
      return false;
    }
    return (
      !term ||
      `${period.name || ""} ${period.description || ""}`
        .toLocaleLowerCase("vi-VN")
        .includes(term)
    );
  });
  if (!periods.length) {
    createStateRow(
      body,
      5,
      (periodsCache || []).length
        ? "Không tìm thấy kỳ thực tập phù hợp."
        : "Backend chưa có kỳ thực tập nào.",
    );
    return;
  }

  body.replaceChildren(
    ...periods.map((period) => {
      const row = document.createElement("tr");
      const nameCell = document.createElement("td");
      const identity = document.createElement("span");
      identity.className = "admin-user-cell";
      const name = document.createElement("strong");
      name.textContent = period.name || "—";
      const description = document.createElement("span");
      description.textContent = period.description || `ID ${period.id}`;
      identity.append(name, description);
      nameCell.append(identity);

      const statusCell = document.createElement("td");
      const statusSelect = document.createElement("select");
      statusSelect.className = "admin-inline-select";
      statusSelect.dataset.periodStatus = "";
      statusSelect.dataset.periodId = String(period.id);
      for (const [value, label] of Object.entries(PERIOD_STATUS_LABELS)) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        option.selected = period.status === value;
        statusSelect.append(option);
      }
      statusCell.append(statusSelect);

      const actionsCell = document.createElement("td");
      const actions = document.createElement("div");
      actions.className = "admin-row-actions";
      for (const [label, action] of [
        ["Chi tiết", "view"],
        ["Sửa", "edit"],
        ["Xóa", "delete"],
      ]) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `admin-row-action${action === "delete" ? " admin-row-action-danger" : ""}`;
        button.dataset.periodAction = action;
        button.dataset.periodId = String(period.id);
        button.textContent = label;
        actions.append(button);
      }
      actionsCell.append(actions);
      row.append(
        nameCell,
        createTextCell(formatDate(period.start_date)),
        createTextCell(formatDate(period.end_date)),
        statusCell,
        actionsCell,
      );
      return row;
    }),
  );
  body.setAttribute("aria-busy", "false");
}

async function loadPeriodsView(force = false) {
  const body = document.querySelector("[data-periods-rows]");
  if (body instanceof HTMLTableSectionElement) {
    createStateRow(body, 5, "Đang tải kỳ thực tập...", "loading");
  }
  await getPeriods(force);
  renderPeriods();
}

async function renderView(view, force = false) {
  clearAlert();
  if (main instanceof HTMLElement) {
    main.setAttribute("aria-busy", "true");
  }
  try {
    if (view === "overview") {
      await loadOverview(force);
    } else if (["users", "supervisors", "students"].includes(view)) {
      await loadUsersView(force);
    } else if (view === "periods") {
      await loadPeriodsView(force);
    }
  } catch (error) {
    showAlert(getErrorMessage(error));
    if (view === "users" || view === "supervisors" || view === "students") {
      for (const selector of ["[data-users-rows]", "[data-supervisors-rows]", "[data-students-rows]"]) {
        const body = document.querySelector(selector);
        if (body instanceof HTMLTableSectionElement) {
          createStateRow(body, 5, getErrorMessage(error), "error");
        }
      }
    } else if (view === "periods") {
      const body = document.querySelector("[data-periods-rows]");
      if (body instanceof HTMLTableSectionElement) {
        createStateRow(body, 5, getErrorMessage(error), "error");
      }
    }
  } finally {
    if (main instanceof HTMLElement) {
      main.setAttribute("aria-busy", "false");
    }
  }
}

function updateSearchForView(view) {
  if (!(searchWrap instanceof HTMLElement) || !(searchInput instanceof HTMLInputElement)) {
    return;
  }
  searchWrap.hidden = !SEARCH_VIEWS.has(view);
  const placeholders = {
    users: "Tìm theo họ tên hoặc email...",
    supervisors: "Tìm tên, email, mã giảng viên...",
    students: "Tìm tên, email, mã sinh viên...",
    periods: "Tìm kỳ thực tập...",
  };
  searchInput.placeholder = placeholders[view] || "Tìm kiếm...";
}

function setView(view) {
  if (!Object.hasOwn(VIEW_LABELS, view)) {
    return;
  }
  currentView = view;
  if (window.location.hash !== `#${view}`) {
    window.location.hash = view;
  }
  for (const panel of document.querySelectorAll("[data-view-panel]")) {
    panel.hidden = panel.dataset.viewPanel !== view;
  }
  for (const link of document.querySelectorAll("[data-view-target]")) {
    const active = link.dataset.viewTarget === view;
    link.classList.toggle("is-active", active);
    if (link instanceof HTMLAnchorElement) {
      if (active) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    }
  }
  const title = document.querySelector("[data-topbar-title]");
  if (title) {
    title.textContent = VIEW_LABELS[view];
  }
  updateSearchForView(view);
  document.body.classList.remove("sidebar-open");
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (toggle instanceof HTMLButtonElement) {
    toggle.setAttribute("aria-expanded", "false");
  }
  void renderView(view);
}

function setupNavigation() {
  window.addEventListener("hashchange", () => {
    const view = window.location.hash.slice(1);
    if (Object.hasOwn(VIEW_LABELS, view) && view !== currentView) {
      setView(view);
    }
  });

  document.querySelectorAll("[data-view-target]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = link.dataset.viewTarget;
      if (target) {
        setView(target);
      }
    });
  });

  document.querySelectorAll("[data-refresh-view]").forEach((button) => {
    button.addEventListener("click", () => void renderView(currentView, true));
  });

  if (searchInput instanceof HTMLInputElement) {
    searchInput.addEventListener("input", () => {
      if (currentView === "users" || currentView === "supervisors" || currentView === "students") {
        renderUserViews();
      } else if (currentView === "periods") {
        renderPeriods();
      }
    });
  }
  for (const selector of [
    "[data-user-role-filter]",
    "[data-user-status-filter]",
    "[data-people-status-filter]",
  ]) {
    document.querySelectorAll(selector).forEach((control) => {
      control.addEventListener("change", renderUserViews);
    });
  }
  document.querySelector("[data-period-status-filter]")?.addEventListener("change", renderPeriods);

  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  const backdrop = document.querySelector("[data-sidebar-backdrop]");
  if (sidebarToggle instanceof HTMLButtonElement && backdrop instanceof HTMLElement) {
    const setOpen = (open) => {
      document.body.classList.toggle("sidebar-open", open);
      sidebarToggle.setAttribute("aria-expanded", String(open));
      sidebarToggle.setAttribute("aria-label", open ? "Đóng menu điều hướng" : "Mở menu điều hướng");
    };
    sidebarToggle.addEventListener("click", () => {
      setOpen(!document.body.classList.contains("sidebar-open"));
    });
    backdrop.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    });
  }
}

function getInitials(name) {
  if (typeof name !== "string" || !name.trim()) {
    return "AD";
  }
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => Array.from(part)[0].toLocaleUpperCase("vi-VN"))
    .join("");
}

function setupAccount(user) {
  document.querySelectorAll("[data-user-name]").forEach((element) => {
    element.textContent = user.full_name || "Quản trị viên";
  });
  document.querySelectorAll("[data-user-role]").forEach((element) => {
    element.textContent = ROLE_LABELS[user.role] || user.role || "ADMIN";
  });
  const initials = document.querySelector("[data-user-initials]");
  if (initials) {
    initials.textContent = getInitials(user.full_name);
  }

  const accountMenu = document.querySelector("[data-account-menu]");
  const accountToggle = document.querySelector("[data-account-toggle]");
  const menu = document.querySelector("#account-menu");
  if (
    accountMenu instanceof HTMLElement &&
    accountToggle instanceof HTMLButtonElement &&
    menu instanceof HTMLElement
  ) {
    const setOpen = (open) => {
      menu.hidden = !open;
      accountToggle.setAttribute("aria-expanded", String(open));
    };
    accountToggle.addEventListener("click", () => setOpen(menu.hidden));
    document.addEventListener("click", (event) => {
      if (event.target instanceof Node && !accountMenu.contains(event.target)) {
        setOpen(false);
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) {
        setOpen(false);
        accountToggle.focus();
      }
    });
  }

  const accountValues = {
    "[data-system-name]": user.full_name || "—",
    "[data-system-email]": user.email || "—",
    "[data-system-role]": ROLE_LABELS[user.role] || user.role || "—",
    "[data-system-id]": user.id === undefined ? "—" : String(user.id),
    "[data-system-session]": `${getAuthSessionPersistence()} Token không hiển thị trên trang.`,
  };
  for (const [selector, value] of Object.entries(accountValues)) {
    const element = document.querySelector(selector);
    if (element) {
      element.textContent = value;
    }
  }
}

function createDetailItem(label, value) {
  const item = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent =
    value === null || value === undefined || value === "" ? "—" : String(value);
  item.append(term, description);
  return item;
}

async function showUserDetails(id) {
  const user = await apiRequest(`users/${id}`);
  const list = document.querySelector("[data-detail-list]");
  const title = document.querySelector("[data-detail-title]");
  const subtitle = document.querySelector("[data-detail-subtitle]");
  if (!(list instanceof HTMLElement) || !(detailDialog instanceof HTMLDialogElement)) {
    return;
  }
  const items = [
    ["ID", user.id],
    ["Họ tên", user.full_name],
    ["Email", user.email],
    ["Vai trò", ROLE_LABELS[user.role] || user.role],
    ["Trạng thái", user.is_active ? "Đang hoạt động" : "Đã khóa"],
    ["Điện thoại", user.phone],
    ["Ngày tạo", formatDateTime(user.created_at)],
    ["Cập nhật gần nhất", formatDateTime(user.updated_at)],
  ];
  if (user.student_profile) {
    items.push(
      ["Mã sinh viên", user.student_profile.student_code],
      ["Lớp", user.student_profile.class_name],
      ["Ngành", user.student_profile.major],
      ["Điện thoại hồ sơ", user.student_profile.phone],
    );
  }
  if (user.lecturer_profile) {
    items.push(
      ["Mã giảng viên", user.lecturer_profile.lecturer_code],
      ["Khoa / bộ môn", user.lecturer_profile.department],
      ["Điện thoại hồ sơ", user.lecturer_profile.phone],
    );
  }
  title.textContent = "Chi tiết người dùng";
  subtitle.textContent = "Thông tin lấy từ GET /users/{user_id}.";
  list.replaceChildren(...items.map(([label, value]) => createDetailItem(label, value)));
  detailDialog.showModal();
}

function setUserProfileFields(role, editing) {
  for (const fieldset of document.querySelectorAll("[data-profile-fields]")) {
    const active = !editing && fieldset.dataset.profileFields === role;
    fieldset.hidden = !active;
    fieldset.disabled = !active;
    const codeInput = fieldset.querySelector(
      fieldset.dataset.profileFields === "STUDENT" ? "#student-code" : "#lecturer-code",
    );
    if (codeInput instanceof HTMLInputElement) {
      codeInput.required = active;
    }
  }
}

function openUserDialog(user = null) {
  if (!(userDialog instanceof HTMLDialogElement) || !(userForm instanceof HTMLFormElement)) {
    return;
  }
  userForm.reset();
  const editing = Boolean(user);
  userForm.dataset.userId = user ? String(user.id) : "";
  const title = document.querySelector("[data-user-dialog-title]");
  const submit = document.querySelector("[data-user-submit]");
  const roleInput = document.querySelector("#user-role");
  const passwordInput = document.querySelector("#user-password");
  const phoneInput = document.querySelector("#user-phone");
  const roleLabel = roleInput?.closest("label");
  if (!(roleInput instanceof HTMLSelectElement) || !(passwordInput instanceof HTMLInputElement)) {
    return;
  }

  if (title) {
    title.textContent = editing ? "Chỉnh sửa người dùng" : "Thêm người dùng";
  }
  if (submit instanceof HTMLButtonElement) {
    submit.textContent = editing ? "Lưu thay đổi" : "Tạo người dùng";
  }
  if (roleLabel instanceof HTMLLabelElement) {
    roleLabel.hidden = editing;
  }
  roleInput.disabled = editing;
  passwordInput.required = !editing;
  passwordInput.disabled = editing;
  document.querySelectorAll("[data-create-only]").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.hidden = editing;
    }
  });
  setUserProfileFields(roleInput.value, editing);

  if (user) {
    const fullName = document.querySelector("#user-full-name");
    const email = document.querySelector("#user-email");
    if (fullName instanceof HTMLInputElement) {
      fullName.value = user.full_name || "";
    }
    if (email instanceof HTMLInputElement) {
      email.value = user.email || "";
    }
    if (phoneInput instanceof HTMLInputElement) {
      phoneInput.value = user.phone || "";
    }
  }
  setFormMessage(document.querySelector("[data-user-form-message]"), "");
  userDialog.showModal();
}

function readFormValue(form, name) {
  const control = form.elements.namedItem(name);
  return control instanceof HTMLInputElement ||
    control instanceof HTMLSelectElement ||
    control instanceof HTMLTextAreaElement
    ? control.value.trim()
    : "";
}

async function submitUserForm(event) {
  event.preventDefault();
  if (!(userForm instanceof HTMLFormElement)) {
    return;
  }
  const message = document.querySelector("[data-user-form-message]");
  const submit = userForm.querySelector('button[type="submit"]');
  const userId = userForm.dataset.userId;
  const editing = Boolean(userId);
  const email = readFormValue(userForm, "email");
  const fullName = readFormValue(userForm, "full_name");
  const phone = readFormValue(userForm, "phone");
  let body;

  if (editing) {
    body = { email, full_name: fullName, phone: phone || null };
  } else {
    const password = readFormValue(userForm, "password");
    const role = readFormValue(userForm, "role");
    if (new TextEncoder().encode(password).length > 72) {
      setFormMessage(message, "Mật khẩu không được vượt quá 72 byte UTF-8.");
      return;
    }
    body = {
      email,
      password,
      full_name: fullName,
      phone: phone || null,
      role,
    };
    if (role === "STUDENT") {
      body.student_profile = {
        student_code: readFormValue(userForm, "student_code"),
        class_name: readFormValue(userForm, "class_name") || null,
        major: readFormValue(userForm, "major") || null,
        phone: readFormValue(userForm, "student_phone") || null,
      };
    } else if (role === "SUPERVISOR") {
      body.lecturer_profile = {
        lecturer_code: readFormValue(userForm, "lecturer_code"),
        department: readFormValue(userForm, "department") || null,
        phone: readFormValue(userForm, "lecturer_phone") || null,
      };
    }
  }

  if (submit instanceof HTMLButtonElement) {
    submit.disabled = true;
  }
  setFormMessage(message, "");
  try {
    await apiRequest(editing ? `users/${userId}` : "users", {
      method: editing ? "PUT" : "POST",
      body,
    });
    userDialog.close();
    usersCache = null;
    showAlert(editing ? "Đã cập nhật thông tin người dùng." : "Đã tạo người dùng mới.", "success");
    await renderView(currentView, true);
  } catch (error) {
    setFormMessage(message, getErrorMessage(error));
  } finally {
    if (submit instanceof HTMLButtonElement) {
      submit.disabled = false;
    }
  }
}

async function handleUserAction(action, id) {
  if (action === "view") {
    await showUserDetails(id);
    return;
  }
  const user = (usersCache || []).find((item) => Number(item.id) === id);
  if (!user) {
    showAlert("Không tìm thấy người dùng trong danh sách hiện tại.");
    return;
  }
  if (action === "edit") {
    openUserDialog(user);
    return;
  }
  if (Number(adminUser?.id) === id) {
    showAlert("Không thể khóa hoặc xóa tài khoản quản trị đang đăng nhập.");
    return;
  }
  if (action === "status") {
    const isActive = !user.is_active;
    if (!await confirmAction({
      title: isActive ? "Kích hoạt tài khoản" : "Khóa tài khoản",
      message: `Xác nhận ${isActive ? "kích hoạt" : "khóa"} tài khoản ${user.email}?`,
      confirmLabel: isActive ? "Kích hoạt" : "Khóa tài khoản",
      destructive: !isActive,
    })) {
      return;
    }
    await apiRequest(`users/${id}/status`, {
      method: "PATCH",
      body: { is_active: isActive },
    });
    usersCache = null;
    showAlert(`Đã ${isActive ? "kích hoạt" : "khóa"} tài khoản.`, "success");
    await renderView(currentView, true);
    return;
  }
  if (action === "delete") {
    if (!await confirmAction({
      title: "Xóa tài khoản",
      message: `Xóa tài khoản ${user.email}? Thao tác này không thể hoàn tác.`,
      confirmLabel: "Xóa người dùng",
      destructive: true,
    })) {
      return;
    }
    await apiRequest(`users/${id}`, { method: "DELETE" });
    usersCache = null;
    showAlert("Đã xóa tài khoản.", "success");
    await renderView(currentView, true);
  }
}

function setupUserActions() {
  for (const selector of [
    "[data-users-rows]",
    "[data-supervisors-rows]",
    "[data-students-rows]",
  ]) {
    const body = document.querySelector(selector);
    body?.addEventListener("click", (event) => {
      const button = event.target instanceof Element
        ? event.target.closest("button[data-user-action]")
        : null;
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const id = Number(button.dataset.userId);
      if (!Number.isInteger(id) || id < 1) {
        showAlert("Mã người dùng không hợp lệ.");
        return;
      }
      void handleUserAction(button.dataset.userAction, id).catch((error) => {
        showAlert(getErrorMessage(error));
      });
    });
  }

  document.querySelector("[data-create-user]")?.addEventListener("click", () => openUserDialog());
  userForm?.addEventListener("submit", (event) => void submitUserForm(event));
  document.querySelector("#user-role")?.addEventListener("change", (event) => {
    const select = event.currentTarget;
    if (select instanceof HTMLSelectElement) {
      setUserProfileFields(select.value, false);
    }
  });
}

function formatReportDeadline(value) {
  return typeof value === "string" && value ? value.slice(0, 16) : "";
}

function openPeriodDialog(period = null) {
  if (!(periodDialog instanceof HTMLDialogElement) || !(periodForm instanceof HTMLFormElement)) {
    return;
  }
  periodForm.reset();
  const editing = Boolean(period);
  periodForm.dataset.periodId = period ? String(period.id) : "";
  const title = document.querySelector("[data-period-dialog-title]");
  const submit = document.querySelector("[data-period-submit]");
  const statusInput = document.querySelector("#period-status");
  if (title) {
    title.textContent = editing ? "Chỉnh sửa kỳ thực tập" : "Thêm kỳ thực tập";
  }
  if (submit instanceof HTMLButtonElement) {
    submit.textContent = editing ? "Lưu thay đổi" : "Tạo kỳ thực tập";
  }
  const statusLabel = statusInput?.closest("label");
  if (statusLabel instanceof HTMLLabelElement) {
    statusLabel.hidden = editing;
  }
  if (period) {
    const values = {
      "#period-name": period.name,
      "#period-description": period.description || "",
      "#period-start-date": period.start_date,
      "#period-end-date": period.end_date,
      "#period-report-deadline": formatReportDeadline(period.report_deadline),
    };
    for (const [selector, value] of Object.entries(values)) {
      const input = document.querySelector(selector);
      if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
        input.value = value || "";
      }
    }
  }
  setFormMessage(document.querySelector("[data-period-form-message]"), "");
  periodDialog.showModal();
}

function readPeriodFormBody() {
  if (!(periodForm instanceof HTMLFormElement)) {
    return null;
  }
  const reportDeadline = readFormValue(periodForm, "report_deadline");
  return {
    name: readFormValue(periodForm, "name"),
    description: readFormValue(periodForm, "description") || null,
    start_date: readFormValue(periodForm, "start_date"),
    end_date: readFormValue(periodForm, "end_date"),
    report_deadline: reportDeadline ? `${reportDeadline}:00` : null,
  };
}

async function submitPeriodForm(event) {
  event.preventDefault();
  if (!(periodForm instanceof HTMLFormElement)) {
    return;
  }
  const message = document.querySelector("[data-period-form-message]");
  const submit = periodForm.querySelector('button[type="submit"]');
  const periodId = periodForm.dataset.periodId;
  const editing = Boolean(periodId);
  const body = readPeriodFormBody();
  if (!body) {
    return;
  }
  if (body.end_date < body.start_date) {
    setFormMessage(message, "Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.");
    return;
  }
  if (!editing) {
    body.status = readFormValue(periodForm, "status");
  }
  if (submit instanceof HTMLButtonElement) {
    submit.disabled = true;
  }
  setFormMessage(message, "");
  try {
    await apiRequest(editing ? `internship-periods/${periodId}` : "internship-periods", {
      method: editing ? "PUT" : "POST",
      body,
    });
    periodDialog.close();
    periodsCache = null;
    showAlert(editing ? "Đã cập nhật kỳ thực tập." : "Đã tạo kỳ thực tập.", "success");
    await renderView(currentView, true);
  } catch (error) {
    setFormMessage(message, getErrorMessage(error));
  } finally {
    if (submit instanceof HTMLButtonElement) {
      submit.disabled = false;
    }
  }
}

function showPeriodDetails(period) {
  const list = document.querySelector("[data-detail-list]");
  const title = document.querySelector("[data-detail-title]");
  const subtitle = document.querySelector("[data-detail-subtitle]");
  if (!(list instanceof HTMLElement) || !(detailDialog instanceof HTMLDialogElement)) {
    return;
  }
  title.textContent = period.name || "Chi tiết kỳ thực tập";
  subtitle.textContent = "Thông tin lấy từ GET /internship-periods.";
  const items = [
    ["ID", period.id],
    ["Tên kỳ thực tập", period.name],
    ["Mô tả", period.description],
    ["Ngày bắt đầu", formatDate(period.start_date)],
    ["Ngày kết thúc", formatDate(period.end_date)],
    ["Hạn nộp báo cáo", formatDateTime(period.report_deadline)],
    ["Trạng thái", PERIOD_STATUS_LABELS[period.status] || period.status],
  ];
  list.replaceChildren(...items.map(([label, value]) => createDetailItem(label, value)));
  detailDialog.showModal();
}

async function handlePeriodAction(action, id) {
  const period = (periodsCache || []).find((item) => Number(item.id) === id);
  if (!period) {
    showAlert("Không tìm thấy kỳ thực tập trong danh sách hiện tại.");
    return;
  }
  if (action === "view") {
    showPeriodDetails(period);
  } else if (action === "edit") {
    openPeriodDialog(period);
  } else if (action === "delete" && await confirmAction({
    title: "Xóa kỳ thực tập",
    message: `Xóa kỳ thực tập “${period.name}”? Backend có thể từ chối nếu kỳ đã gắn với nhóm.`,
    confirmLabel: "Xóa kỳ thực tập",
    destructive: true,
  })) {
    await apiRequest(`internship-periods/${id}`, { method: "DELETE" });
    periodsCache = null;
    showAlert("Đã xóa kỳ thực tập.", "success");
    await renderView(currentView, true);
  }
}

function setupPeriodActions() {
  document.querySelector("[data-create-period]")?.addEventListener("click", () => openPeriodDialog());
  periodForm?.addEventListener("submit", (event) => void submitPeriodForm(event));
  const body = document.querySelector("[data-periods-rows]");
  body?.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("button[data-period-action]")
      : null;
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const id = Number(button.dataset.periodId);
    if (!Number.isInteger(id) || id < 1) {
      showAlert("Mã kỳ thực tập không hợp lệ.");
      return;
    }
    void handlePeriodAction(button.dataset.periodAction, id).catch((error) => {
      showAlert(getErrorMessage(error));
    });
  });
  body?.addEventListener("change", (event) => {
    const select = event.target;
    if (!(select instanceof HTMLSelectElement) || !select.matches("[data-period-status]")) {
      return;
    }
    const id = Number(select.dataset.periodId);
    if (!Number.isInteger(id) || id < 1) {
      showAlert("Mã kỳ thực tập không hợp lệ.");
      return;
    }
    void apiRequest(`internship-periods/${id}/status`, {
      method: "PATCH",
      body: { status: select.value },
    })
      .then(async () => {
        periodsCache = null;
        showAlert("Đã cập nhật trạng thái kỳ thực tập.", "success");
        await renderView(currentView, true);
      })
      .catch((error) => {
        showAlert(getErrorMessage(error));
        void renderPeriods();
      });
  });
}

function setupDialogs() {
  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      const dialog = button.closest("dialog");
      if (dialog instanceof HTMLDialogElement) {
        dialog.close();
      }
    });
  });
  for (const dialog of [userDialog, detailDialog, periodDialog]) {
    if (dialog instanceof HTMLDialogElement) {
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
          dialog.close();
        }
      });
    }
  }
}

function setupPasswordChange() {
  const form = document.querySelector("[data-password-form]");
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const currentPassword = form.elements.namedItem("current_password");
    const newPassword = form.elements.namedItem("new_password");
    const confirmation = form.elements.namedItem("confirm_password");
    const message = document.querySelector("[data-password-message]");
    const submit = form.querySelector('button[type="submit"]');
    if (
      !(currentPassword instanceof HTMLInputElement) ||
      !(newPassword instanceof HTMLInputElement) ||
      !(confirmation instanceof HTMLInputElement)
    ) {
      return;
    }
    if (newPassword.value !== confirmation.value) {
      setFormMessage(message, "Mật khẩu xác nhận không khớp.");
      confirmation.focus();
      return;
    }
    if (new TextEncoder().encode(newPassword.value).length > 72) {
      setFormMessage(message, "Mật khẩu mới không được vượt quá 72 byte UTF-8.");
      newPassword.focus();
      return;
    }

    if (submit instanceof HTMLButtonElement) {
      submit.disabled = true;
    }
    setFormMessage(message, "Đang cập nhật mật khẩu...", "success");
    try {
      await apiRequest("auth/change-password", {
        method: "PUT",
        body: {
          current_password: currentPassword.value,
          new_password: newPassword.value,
        },
      });
      form.reset();
      setFormMessage(message, "Đã đổi mật khẩu thành công.", "success");
    } catch (error) {
      setFormMessage(message, getErrorMessage(error));
    } finally {
      if (submit instanceof HTMLButtonElement) {
        submit.disabled = false;
      }
    }
  });
}

function setupLogout() {
  document.querySelectorAll("[data-logout], [data-system-logout]").forEach((button) => {
    button.addEventListener("click", logout);
  });
}

async function initializeAdmin() {
  try {
    adminUser = await requireAuth();
    if (!adminUser) {
      return;
    }
    await initializeSharedUi();
    setupAccount(adminUser);
    setupNavigation();
    setupUserActions();
    setupPeriodActions();
    setupDialogs();
    setupPasswordChange();
    setupLogout();
    const requestedView = window.location.hash.slice(1);
    setView(Object.hasOwn(VIEW_LABELS, requestedView) ? requestedView : "overview");
  } catch (error) {
    showAlert(getErrorMessage(error));
    if (main instanceof HTMLElement) {
      main.setAttribute("aria-busy", "false");
    }
  }
}

void initializeAdmin();
