import { API_BASE_URL, apiRequest, getAccessToken } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeSharedUi, showToast } from "./ui.js";
import { renderTaskDashboard, showTaskDashboardError } from "./student-dashboard.js";

export function getTasks() {
  return apiRequest("tasks");
}

export function getTaskComments(taskId) {
  return apiRequest(`tasks/${taskId}/comments`);
}

export function createTaskComment(taskId, content) {
  return apiRequest(`tasks/${taskId}/comments`, {
    method: "POST",
    body: { content },
  });
}

export function getTaskAttachments(taskId) {
  return apiRequest(`attachments?task_id=${encodeURIComponent(taskId)}`);
}

export function uploadTaskEvidence(taskId, file) {
  const body = new FormData();
  body.set("task_id", String(taskId));
  body.set("file", file);
  return apiRequest("attachments/upload", { method: "POST", body });
}

export function createTask(payload) {
  return apiRequest("tasks", { method: "POST", body: payload });
}

export function assignTask(taskId, studentId) {
  return apiRequest(`tasks/${taskId}/assign`, {
    method: "PUT",
    body: Array.isArray(studentId) ? { student_ids: studentId } : { student_id: studentId },
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

export function getMyTaskProgress(taskId) {
  return apiRequest(`tasks/${taskId}/progress`);
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
    studentTasks = normalizeTasks(payload);
    const applyFilters = () => {
      const status = document.querySelector("[data-student-task-status]")?.value || "";
      const priority = document.querySelector("[data-student-task-priority]")?.value || "";
      const filtered = studentTasks.filter((task) =>
        (!status || task.status === status) &&
        (!priority || task.priority === priority));
      renderTaskDashboard(filtered);
    };
    if (!studentTaskFiltersBound) {
      document.querySelector("[data-student-task-status]")?.addEventListener("change", applyFilters);
      document.querySelector("[data-student-task-priority]")?.addEventListener("change", applyFilters);
      studentTaskFiltersBound = true;
    }
    applyFilters();
  } catch (error) {
    showTaskDashboardError();
  }
}

let supervisorTasks = [];
let studentTasks = [];
let activeTaskId = null;
let activeDetailTask = null;
let studentTaskFiltersBound = false;

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
    const detailButton = document.createElement("button");
    detailButton.type = "button";
    detailButton.className = "admin-row-action";
    detailButton.dataset.taskDetailId = String(task.id);
    detailButton.textContent = "Chi tiết";
    const statusButton = document.createElement("button");
    statusButton.type = "button";
    statusButton.className = "admin-row-action";
    statusButton.dataset.taskStatusId = String(task.id);
    statusButton.textContent = "Trạng thái";
    statusButton.disabled = task.status !== "REVIEW";
    actions.append(detailButton, statusButton);
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
  assigneeSelect.replaceChildren();
  assigneeSelect.disabled = false;
  if (!teamSelect.value) return;
  try {
    const members = await apiRequest(`teams/${teamSelect.value}/members`);
    assigneeSelect.replaceChildren(
      ...(Array.isArray(members) ? members : []).map((member) => {
        const label = member.student_name
          ? `${member.student_name}${member.student_code ? ` (${member.student_code})` : ""}`
          : `Sinh viên ID ${member.student_id}`;
        return new Option(label, String(member.student_id));
      }),
    );
  } catch (error) {
    assigneeSelect.replaceChildren(new Option("Không tải được danh sách thành viên", "", true, true));
    assigneeSelect.disabled = true;
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

function taskProgress(task) {
  const assignments = Array.isArray(task.assignments) ? task.assignments : [];
  if (!assignments.length) return task.status === "DONE" ? 100 : 0;
  return Math.round(assignments.reduce((sum, item) => sum + (Number(item.progress) || 0), 0) / assignments.length);
}

function renderDetailItems(container, items, renderItem, emptyMessage) {
  if (!container) return;
  if (!Array.isArray(items) || !items.length) {
    const empty = document.createElement("li");
    empty.textContent = emptyMessage;
    container.replaceChildren(empty);
    return;
  }
  container.replaceChildren(...items.map(renderItem));
}

function renderTaskComments(comments) {
  renderDetailItems(
    document.querySelector("[data-task-detail-comments]"),
    comments,
    (comment) => {
      const item = document.createElement("li");
      const heading = document.createElement("strong");
      heading.textContent = comment.user_name || `Thành viên #${comment.user_id}`;
      const date = document.createElement("time");
      date.textContent = formatDeadline(comment.created_at);
      const content = document.createElement("p");
      content.textContent = comment.content;
      item.append(heading, date, content);
      return item;
    },
    "Chưa có bình luận.",
  );
}

function renderTaskAttachments(attachments) {
  renderDetailItems(
    document.querySelector("[data-task-detail-attachments]"),
    attachments,
    (attachment) => {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = attachment.file_name;
      const download = document.createElement("button");
      download.type = "button";
      download.className = "admin-row-action";
      download.dataset.attachmentId = String(attachment.id);
      download.textContent = "Tải xuống";
      item.append(name, download);
      return item;
    },
    "Chưa có minh chứng.",
  );
}

async function configureStudentTaskForm(task) {
  const section = document.querySelector("[data-student-task-update-section]");
  const form = document.querySelector("[data-student-task-update-form]");
  if (!section || !(form instanceof HTMLFormElement)) return;
  const isStudent = document.body?.dataset.myTasksPage !== undefined;
  const canUpdate = isStudent && task.status !== "DONE" && task.status !== "CANCELLED";
  section.hidden = !canUpdate;
  if (!canUpdate) return;

  form.elements.progress.value = String(taskProgress(task));
  const statusSelect = form.elements.status;
  const options = [new Option("Không đổi trạng thái", "")];
  if (task.status === "TODO") options.push(new Option("Đang thực hiện", "IN_PROGRESS"));
  if (task.status === "IN_PROGRESS") options.push(new Option("Chờ duyệt", "REVIEW"));
  statusSelect.replaceChildren(...options);
  try {
    const assignment = await getMyTaskProgress(task.id);
    if (activeDetailTask?.id === task.id) {
      form.elements.progress.value = String(assignment.progress);
    }
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

async function openTaskDetails(taskId) {
  const task = [...supervisorTasks, ...studentTasks].find((item) => Number(item.id) === taskId);
  const dialog = document.querySelector("[data-task-detail-dialog]");
  if (!task || !(dialog instanceof HTMLDialogElement)) return;
  activeDetailTask = task;
  document.querySelector("[data-task-detail-title]").textContent = task.title;
  document.querySelector("[data-task-detail-status]").textContent = task.status;
  document.querySelector("[data-task-detail-deadline]").textContent = formatDeadline(task.deadline);
  document.querySelector("[data-task-detail-progress]").textContent = `${taskProgress(task)}%`;
  document.querySelector("[data-task-detail-priority]").textContent = task.priority;
  document.querySelector("[data-task-detail-description]").textContent = task.description || "Không có mô tả.";
  const assignees = Array.isArray(task.assignments) ? task.assignments : [];
  document.querySelector("[data-task-detail-assignees]").textContent = assignees.length
    ? assignees.map((item) => item.student_name || item.student_code || `Sinh viên #${item.student_id}`).join(", ")
    : "Chưa giao";
  void configureStudentTaskForm(task);
  const commentsList = document.querySelector("[data-task-detail-comments]");
  const attachmentsList = document.querySelector("[data-task-detail-attachments]");
  commentsList.replaceChildren(Object.assign(document.createElement("li"), { textContent: "Đang tải..." }));
  attachmentsList.replaceChildren(Object.assign(document.createElement("li"), { textContent: "Đang tải..." }));
  if (!dialog.open) dialog.showModal();

  const [comments, attachments] = await Promise.allSettled([
    getTaskComments(taskId),
    getTaskAttachments(taskId),
  ]);
  if (activeDetailTask?.id !== taskId) return;
  if (comments.status === "fulfilled") {
    renderTaskComments(comments.value);
  } else {
    renderTaskComments([]);
    commentsList.firstElementChild.textContent = "Không tải được bình luận.";
    showToast(comments.reason.message, { kind: "error" });
  }
  if (attachments.status === "fulfilled") {
    renderTaskAttachments(attachments.value);
  } else {
    renderTaskAttachments([]);
    attachmentsList.firstElementChild.textContent = "Không tải được minh chứng.";
    showToast(attachments.reason.message, { kind: "error" });
  }
}

async function refreshTaskListAndDetail() {
  if (document.body?.dataset.myTasksPage !== undefined) {
    await loadStudentTasks();
  } else {
    await loadSupervisorTasks();
  }
  if (activeDetailTask) await openTaskDetails(activeDetailTask.id);
}

async function downloadTaskAttachment(attachmentId) {
  const token = getAccessToken();
  const response = await fetch(new URL(`attachments/${attachmentId}`, `${API_BASE_URL}/`), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    let message = `Không thể tải tệp (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") message = payload.detail;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
    throw new Error(message);
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = "";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
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
    const studentIds = Array.from(form.elements.student_ids.selectedOptions)
      .map((option) => Number(option.value))
      .filter((studentId) => studentId > 0);
    if (studentIds.length && createdTask?.id) {
      await assignTask(createdTask.id, studentIds);
    }
    document.querySelector("[data-task-dialog]")?.close();
    showToast("Đã tạo công việc.");
    await loadSupervisorTasks();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-supervisor-task-rows]")?.addEventListener("click", (event) => {
  const detailButton = event.target instanceof Element ? event.target.closest("[data-task-detail-id]") : null;
  if (detailButton instanceof HTMLButtonElement) {
    void openTaskDetails(Number(detailButton.dataset.taskDetailId));
    return;
  }
  const button = event.target instanceof Element ? event.target.closest("[data-task-status-id]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  activeTaskId = Number(button.dataset.taskStatusId);
  const task = supervisorTasks.find((item) => Number(item.id) === activeTaskId);
  if (task) document.querySelector("#task-status").value = "DONE";
  document.querySelector("[data-task-status-dialog]")?.showModal();
});

document.querySelector("[data-task-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-task-detail-id]") : null;
  if (button instanceof HTMLButtonElement) void openTaskDetails(Number(button.dataset.taskDetailId));
});

document.querySelector("[data-student-task-update-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!activeDetailTask) return;
  try {
    await updateTaskProgress(activeDetailTask.id, Number(form.elements.progress.value));
    const newStatus = form.elements.status.value;
    if (newStatus) await updateTaskStatus(activeDetailTask.id, newStatus);
    showToast("Đã cập nhật tiến độ.");
    await refreshTaskListAndDetail();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-task-comment-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!activeDetailTask) return;
  try {
    await createTaskComment(activeDetailTask.id, form.elements.content.value.trim());
    form.reset();
    showToast("Đã gửi bình luận.");
    await openTaskDetails(activeDetailTask.id);
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-task-evidence-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = form.elements.file.files?.[0];
  if (!activeDetailTask || !file) return;
  try {
    await uploadTaskEvidence(activeDetailTask.id, file);
    form.reset();
    showToast("Đã tải minh chứng.");
    await openTaskDetails(activeDetailTask.id);
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-task-detail-dialog]")?.addEventListener("click", async (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-attachment-id]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  try {
    await downloadTaskAttachment(Number(button.dataset.attachmentId));
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
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
  ["[data-task-detail-dialog]", "[data-close-task-detail-dialog]"],
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