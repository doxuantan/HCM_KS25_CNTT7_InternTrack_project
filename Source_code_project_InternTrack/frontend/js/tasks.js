import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeSharedUi, showToast } from "./ui.js";
import { renderTaskDashboard, showTaskDashboardError } from "./student-dashboard.js";

export function getTasks() {
  return apiRequest("tasks");
}

export function createTask(payload) {
  return apiRequest("tasks", { method: "POST", body: payload });
}

export function assignTask(taskId, studentId) {
  return apiRequest(`tasks/${taskId}/assign`, {
    method: "PUT",
    body: { student_id: studentId },
  });
}

export function updateTaskStatus(taskId, status) {
  return apiRequest(`tasks/${taskId}/status`, {
    method: "PUT",
    body: { status },
  });
}

export function updateTaskProgress(taskId, progress) {
  return apiRequest(`tasks/${taskId}/progress`, {
    method: "PATCH",
    body: { progress },
  });
}

export function updateTask(taskId) {
  throw new Error(`API chưa hỗ trợ cập nhật thông tin tổng quát của task ${taskId}.`);
}

export function deleteTask(taskId) {
  throw new Error(`API chưa hỗ trợ xóa task ${taskId}.`);
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function taskStateRow(message, columns = 6) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "admin-table-state";
  cell.textContent = message;
  row.append(cell);
  return row;
}

function normalizeTasks(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  if (payload && Array.isArray(payload.tasks)) return payload.tasks;
  return [];
}

export async function loadStudentTasks() {
  try {
    const payload = await getTasks();
    const tasks = normalizeTasks(payload);
    const sourceTasks = Array.isArray(tasks) ? tasks : [];
    const state = { tasks: sourceTasks };
    const applyFilters = () => {
      const status = document.querySelector("[data-student-task-status]")?.value || "";
      const priority = document.querySelector("[data-student-task-priority]")?.value || "";
      const filtered = state.tasks.filter((task) =>
        (!status || task.status === status) &&
        (!priority || task.priority === priority));
      renderTaskDashboard(filtered);
    };
    document.querySelector("[data-student-task-status]")?.addEventListener("change", applyFilters);
    document.querySelector("[data-student-task-priority]")?.addEventListener("change", applyFilters);
    applyFilters();
  } catch (error) {
    showTaskDashboardError();
  }
}

let supervisorTasks = [];
let activeTaskId = null;

function formatDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Ho_Chi_Minh" }).format(date);
}

function assigneeLabel(task) {
  if (Array.isArray(task.assignments) && task.assignments.length) {
    return task.assignments.map((item) =>
      item.student_name || item.student_code || `Sinh viên ID ${item.student_id}`).join(", ");
  }
  return "Chưa giao";
}

function renderSupervisorTasks() {
  const body = document.querySelector("[data-supervisor-task-rows]");
  if (!body) return;
  const status = document.querySelector("[data-supervisor-task-status]")?.value || "";
  const priority = document.querySelector("[data-supervisor-task-priority]")?.value || "";
  const filtered = supervisorTasks.filter((task) =>
    (!status || task.status === status) &&
    (!priority || task.priority === priority));
  if (!filtered.length) {
    body.replaceChildren(taskStateRow(supervisorTasks.length ? "Không có task phù hợp bộ lọc." : "Chưa có task hoặc API danh sách chưa được backend hỗ trợ.", 6));
    return;
  }
  body.replaceChildren(...filtered.map((task) => {
    const row = document.createElement("tr");
    const title = document.createElement("td");
    title.innerHTML = `<strong>${escapeHtml(task.title)}</strong>${task.description ? `<br><span class="muted">${escapeHtml(task.description)}</span>` : ""}`;
    const assignee = document.createElement("td");
    assignee.textContent = assigneeLabel(task);
    const statusCell = document.createElement("td");
    statusCell.textContent = task.status;
    const priorityCell = document.createElement("td");
    priorityCell.textContent = task.priority;
    const deadline = document.createElement("td");
    deadline.textContent = formatDeadline(task.deadline);
    const actions = document.createElement("td");
    const statusButton = document.createElement("button");
    statusButton.type = "button";
    statusButton.className = "admin-row-action";
    statusButton.dataset.taskStatusId = String(task.id);
    statusButton.textContent = "Trạng thái";
    statusButton.disabled = task.status === "DONE" || task.status === "CANCELLED";
    actions.append(statusButton);
    row.append(title, assignee, statusCell, priorityCell, deadline, actions);
    return row;
  }));
}

async function loadSupervisorTeams() {
  const teams = await apiRequest("teams");
  const select = document.getElementById("task-team");
  if (select) {
    select.replaceChildren(...(Array.isArray(teams) ? teams : []).filter((team) => team.status === "ACTIVE" || !team.status).map((team) => {
      const option = document.createElement("option");
      option.value = String(team.id);
      option.textContent = team.team_name || `Nhóm ID ${team.id}`;
      return option;
    }));
  }
  await loadTaskAssignees();
}

async function loadTaskAssignees() {
  const teamSelect = document.getElementById("task-team");
  const assigneeSelect = document.getElementById("task-assignee");
  if (!(teamSelect instanceof HTMLSelectElement) || !(assigneeSelect instanceof HTMLSelectElement)) return;
  assigneeSelect.replaceChildren(new Option("Chưa giao", ""));
  if (!teamSelect.value) return;
  try {
    const members = await apiRequest(`teams/${teamSelect.value}/members`);
    assigneeSelect.replaceChildren(
      new Option("Chưa giao", ""),
      ...(Array.isArray(members) ? members : []).map((member) => {
        const label = member.student_name
          ? `${member.student_name}${member.student_code ? ` (${member.student_code})` : ""}`
          : `Sinh viên ID ${member.student_id}`;
        return new Option(label, String(member.student_id));
      }),
    );
  } catch (error) {
    assigneeSelect.replaceChildren(new Option("Không tải được danh sách thành viên", ""));
  }
}

async function loadSupervisorTasks() {
  const body = document.querySelector("[data-supervisor-task-rows]");
  if (body) body.replaceChildren(taskStateRow("Đang tải công việc...", 6));
  try {
    const payload = await getTasks();
    supervisorTasks = normalizeTasks(payload);
  } catch (error) {
    supervisorTasks = [];
  }
  renderSupervisorTasks();
}

document.querySelector("[data-supervisor-task-status]")?.addEventListener("change", renderSupervisorTasks);
document.querySelector("[data-supervisor-task-priority]")?.addEventListener("change", renderSupervisorTasks);
document.getElementById("task-team")?.addEventListener("change", () => {
  void loadTaskAssignees();
});
document.querySelector("[data-create-task]")?.addEventListener("click", () => {
  const dialog = document.querySelector("[data-task-dialog]");
  const form = document.querySelector("[data-task-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  form.reset();
  const today = new Date();
  const todayValue = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  form.elements.start_date.value = todayValue;
  dialog.showModal();
});

document.querySelector("[data-task-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const title = form.elements.title.value.trim();
  const startDate = form.elements.start_date.value;
  const deadline = form.elements.deadline.value;
  if (!title || !startDate || !deadline) {
    showToast("Vui lòng nhập đầy đủ tên, ngày bắt đầu và deadline.", { kind: "error" });
    return;
  }
  if (deadline.slice(0, 10) < startDate) {
    showToast("Deadline phải cùng hoặc sau ngày bắt đầu.", { kind: "error" });
    return;
  }
  if (new Date(deadline).getTime() <= Date.now()) {
    showToast("Deadline không được nằm trong quá khứ.", { kind: "error" });
    return;
  }
  try {
    const createdTask = await createTask({
      team_id: Number(form.elements.team_id.value),
      title,
      description: form.elements.description.value.trim() || null,
      task_type: form.elements.task_type.value,
      priority: form.elements.priority.value,
      start_date: startDate,
      deadline: deadline,
    });
    const studentId = Number(form.elements.student_id.value);
    if (studentId > 0 && createdTask?.id) {
      await assignTask(createdTask.id, studentId);
    }
    document.querySelector("[data-task-dialog]")?.close();
    showToast("Đã tạo công việc.");
    await loadSupervisorTasks();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-supervisor-task-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-task-status-id]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  activeTaskId = Number(button.dataset.taskStatusId);
  document.querySelector("[data-task-status-dialog]")?.showModal();
});

document.querySelector("[data-task-status-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await updateTaskStatus(activeTaskId, form.elements.status.value);
    document.querySelector("[data-task-status-dialog]")?.close();
    showToast("Đã cập nhật trạng thái.");
    await loadSupervisorTasks();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

for (const [dialogSelector, closeSelector] of [
  ["[data-task-dialog]", "[data-close-task-dialog]"],
  ["[data-task-status-dialog]", "[data-close-task-status-dialog]"],
]) {
  const dialog = document.querySelector(dialogSelector);
  document.querySelectorAll(closeSelector).forEach((button) => button.addEventListener("click", () => dialog?.close()));
}

if (document.body?.dataset.myTasksPage !== undefined) {
  const user = await requireAuth();
  if (user) {
    await initializeSharedUi();
    await loadStudentTasks();
  }
  document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
}

if (document.body?.dataset.supervisorTasksPage !== undefined) {
  const user = await requireAuth();
  if (user) {
    await initializeSharedUi();
    await loadSupervisorTeams();
    await loadSupervisorTasks();
  }
  document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
}