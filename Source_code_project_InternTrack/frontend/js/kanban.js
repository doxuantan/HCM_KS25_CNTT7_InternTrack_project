import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeSharedUi, showToast } from "./ui.js";

let currentUser = null;
let allTasks = [];

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function normalizeTasks(payload) {
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload?.items) ? payload.items : [];
}

function formatDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function assigneeLabel(task) {
  if (!Array.isArray(task.assignments) || !task.assignments.length) return "Chưa giao";
  return task.assignments.map((item) =>
    item.student_name || item.student_code || `Sinh viên #${item.student_id}`
  ).join(", ");
}

function kanbanStatus(task) {
  if (task.status === "REVIEW") return "IN_PROGRESS";
  if (task.status === "DONE") return "DONE";
  return task.status === "IN_PROGRESS" ? "IN_PROGRESS" : "TODO";
}

function buildCard(task) {
  const card = document.createElement("article");
  card.className = "kanban-card";
  card.dataset.taskId = String(task.id);
  card.draggable = currentUser?.role !== "STUDENT" || ["TODO", "IN_PROGRESS", "REVIEW"].includes(task.status);
  card.innerHTML = `
    <h3>${escapeHtml(task.title)}</h3>
    ${task.description ? `<p>${escapeHtml(task.description.length > 140 ? `${task.description.slice(0, 137)}...` : task.description)}</p>` : ""}
    <div class="kanban-card-meta">
      <span>Ưu tiên: ${escapeHtml(task.priority)}</span>
      <span>Hạn: ${escapeHtml(formatDeadline(task.deadline))}</span>
      <span>Người giao: ${escapeHtml(assigneeLabel(task))}</span>
    </div>
  `;

  if (card.draggable) {
    card.addEventListener("dragstart", () => {
      card.classList.add("dragging");
      card.dataset.dragging = "true";
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
  }

  const mobileSelect = document.createElement("select");
  mobileSelect.className = "form-control";
  mobileSelect.setAttribute("aria-label", `Chuyển trạng thái ${task.title}`);
  mobileSelect.innerHTML = `
    <option value="TODO">To Do</option>
    <option value="IN_PROGRESS">In Progress</option>
    ${currentUser?.role !== "STUDENT" ? '<option value="DONE">Done</option>' : '<option value="REVIEW">Chờ duyệt</option>'}
  `;
  mobileSelect.value = task.status === "REVIEW" ? "IN_PROGRESS" : task.status;
  mobileSelect.addEventListener("change", () => {
    const selected = mobileSelect.value === "IN_PROGRESS" && task.status === "REVIEW"
      ? "IN_PROGRESS"
      : mobileSelect.value;
    void moveTask(task.id, selected);
  });
  card.append(mobileSelect);
  return card;
}

function getFilters() {
  return {
    q: document.querySelector("[data-kanban-search]")?.value.trim() || "",
    status: document.querySelector("[data-kanban-status]")?.value || "",
    priority: document.querySelector("[data-kanban-priority]")?.value || "",
    sort: document.querySelector("[data-kanban-sort]")?.value || "created_desc",
  };
}

function applyLocalFilters() {
  const filters = getFilters();
  const filtered = allTasks.filter((task) => {
    const haystack = `${task.title || ""} ${task.description || ""}`.toLowerCase();
    return (!filters.q || haystack.includes(filters.q.toLowerCase()))
      && (!filters.status || task.status === filters.status)
      && (!filters.priority || task.priority === filters.priority);
  });

  const columns = {
    TODO: [],
    IN_PROGRESS: [],
    DONE: [],
  };
  filtered.forEach((task) => columns[kanbanStatus(task)].push(task));

  Object.entries(columns).forEach(([column, tasks]) => {
    const list = document.querySelector(`[data-kanban-list="${column}"]`);
    const count = document.querySelector(`[data-kanban-count="${column}"]`);
    if (count) count.textContent = String(tasks.length);
    if (!list) return;
    list.replaceChildren(
      ...(tasks.length
        ? tasks.map(buildCard)
        : [Object.assign(document.createElement("div"), {
            className: "kanban-empty",
            textContent: "Không có task phù hợp.",
          })])
    );
  });
}

async function loadTasks() {
  const board = document.querySelector("[data-kanban-board]");
  board?.setAttribute("aria-busy", "true");
  try {
    const filters = getFilters();
    const params = new URLSearchParams({ limit: "100", sort: filters.sort });
    if (filters.q) params.set("q", filters.q);
    if (filters.status) params.set("status", filters.status);
    if (filters.priority) params.set("priority", filters.priority);
    allTasks = normalizeTasks(await apiRequest(`tasks?${params}`));
  } catch (error) {
    allTasks = [];
    showToast(error.message, { kind: "error" });
  } finally {
    applyLocalFilters();
    board?.setAttribute("aria-busy", "false");
  }
}

async function moveTask(taskId, newStatus) {
  const task = allTasks.find((item) => item.id === taskId);
  if (!task) return;
  const oldStatus = task.status;
  if (oldStatus === newStatus) return;
  try {
    await apiRequest(`tasks/${taskId}/status`, {
      method: "PUT",
      body: { status: newStatus },
    });
    showToast("Đã cập nhật trạng thái task.");
    await loadTasks();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

document.querySelectorAll("[data-kanban-column]").forEach((column) => {
  column.addEventListener("dragover", (event) => {
    event.preventDefault();
    column.classList.add("is-over");
  });
  column.addEventListener("dragleave", () => column.classList.remove("is-over"));
  column.addEventListener("drop", (event) => {
    event.preventDefault();
    column.classList.remove("is-over");
    const card = document.querySelector(".kanban-card.dragging");
    if (!card) return;
    const target = column.dataset.kanbanColumn;
    const taskId = Number(card.dataset.taskId);
    const task = allTasks.find((item) => item.id === taskId);
    if (!task) return;
    let status = target;
    if (target === "DONE" && currentUser?.role === "STUDENT") status = "REVIEW";
    if (target === "IN_PROGRESS" && task.status === "TODO") status = "IN_PROGRESS";
    if (target === "TODO") status = "TODO";
    void moveTask(taskId, status);
  });
});

document.querySelector("[data-kanban-search]")?.addEventListener("input", () => void loadTasks());
document.querySelector("[data-kanban-status]")?.addEventListener("change", () => void loadTasks());
document.querySelector("[data-kanban-priority]")?.addEventListener("change", () => void loadTasks());
document.querySelector("[data-kanban-sort]")?.addEventListener("change", () => void loadTasks());
document.querySelector("[data-kanban-clear]")?.addEventListener("click", () => {
  document.querySelectorAll("[data-kanban-search], [data-kanban-status], [data-kanban-priority]").forEach((control) => {
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) control.value = "";
  });
  const sort = document.querySelector("[data-kanban-sort]");
  if (sort instanceof HTMLSelectElement) sort.value = "created_desc";
  void loadTasks();
});

currentUser = await requireAuth();
if (currentUser) {
  await initializeSharedUi();
  await loadTasks();
  document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
}
