import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeSharedUi, showToast } from "./ui.js";

const statusLabels = Object.freeze({
  TODO: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thực hiện",
  REVIEW: "Chờ duyệt",
  DONE: "Hoàn thành",
  CANCELLED: "Đã hủy",
});

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
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
}

async function loadProgress() {
  try {
    const [progress, taskPayload] = await Promise.all([
      apiRequest("progress/me"),
      apiRequest("tasks?limit=100"),
    ]);
    const tasks = Array.isArray(taskPayload) ? taskPayload : taskPayload?.items || [];
    const percent = Number(progress.progress || 0);

    setText("[data-progress-total]", String(progress.total_tasks));
    setText("[data-progress-completed]", String(progress.completed_tasks));
    setText("[data-progress-in-progress]", String(progress.in_progress_tasks));
    setText("[data-progress-todo]", String(progress.todo_tasks ?? progress.not_started_tasks));
    setText("[data-progress-percent]", `${percent.toFixed(1)}%`);

    const bar = document.querySelector("[data-progress-bar]");
    const fill = document.querySelector("[data-progress-fill]");
    if (bar instanceof HTMLElement && fill instanceof HTMLElement) {
      bar.setAttribute("aria-valuenow", String(percent));
      bar.setAttribute("aria-valuetext", `${percent.toFixed(1)}% hoàn thành`);
      fill.style.width = `${percent}%`;
    }

    const body = document.querySelector("[data-progress-task-rows]");
    if (!(body instanceof HTMLElement)) return;
    if (!tasks.length) {
      body.innerHTML = '<tr><td colspan="4" class="student-state-cell"><div class="student-state">Chưa có task nào được giao.</div></td></tr>';
      return;
    }
    body.innerHTML = tasks.map((task) => `
      <tr>
        <td><strong>${escapeHtml(task.title)}</strong>${task.description ? `<br><span class="muted">${escapeHtml(task.description)}</span>` : ""}</td>
        <td><span class="student-status student-status-${escapeHtml(String(task.status).toLowerCase().replaceAll("_", "-"))}">${escapeHtml(statusLabels[task.status] || task.status)}</span></td>
        <td>${escapeHtml(task.priority || "—")}</td>
        <td>${escapeHtml(formatDate(task.deadline))}</td>
      </tr>
    `).join("");
  } catch (error) {
    showToast(error.message, { kind: "error" });
    const body = document.querySelector("[data-progress-task-rows]");
    if (body instanceof HTMLElement) {
      body.innerHTML = '<tr><td colspan="4" class="student-state-cell"><div class="student-state" role="alert">Không thể tải dữ liệu tiến độ.</div></td></tr>';
    }
  } finally {
    document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
  }
}

const user = await requireAuth();
if (user) {
  await initializeSharedUi();
  await loadProgress();
}