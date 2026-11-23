<<<<<<< HEAD
const VALID_TASK_STATUSES = new Set(["TODO", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED"]);
const TASK_STATUS_LABELS = Object.freeze({
  TODO: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thực hiện",
  REVIEW: "Chờ duyệt",
  DONE: "Hoàn thành",
  CANCELLED: "Đã hủy",
=======
import { apiRequest } from "./api.js";

const VALID_TASK_STATUSES = new Set(["TODO", "IN_PROGRESS", "DONE"]);
const TASK_STATUS_LABELS = Object.freeze({
  TODO: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thực hiện",
  DONE: "Hoàn thành",
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
});
const TASK_PRIORITIES = Object.freeze({
  LOW: { label: "Thấp", className: "student-priority-low" },
  MEDIUM: { label: "Trung bình", className: "student-priority-medium" },
  HIGH: { label: "Cao", className: "student-priority-high" },
});
<<<<<<< HEAD
const USER_ROLE_LABELS = Object.freeze({
  ADMIN: "Quản trị viên",
  SUPERVISOR: "Giảng viên hướng dẫn",
  STUDENT: "Sinh viên",
});
=======
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18

function isValidTask(task) {
  return (
    task !== null &&
    typeof task === "object" &&
    !Array.isArray(task) &&
    typeof task.title === "string" &&
    task.title.trim().length > 0 &&
    VALID_TASK_STATUSES.has(task.status)
  );
}

export function calculateTaskMetrics(tasks) {
  if (!Array.isArray(tasks)) {
    throw new TypeError("Task data must be an array.");
  }

  const validTasks = tasks.filter(isValidTask);
  const completed = validTasks.filter((task) => task.status === "DONE").length;
  const total = validTasks.length;

  return {
    tasks: validTasks,
    total,
    completed,
    inProgress: validTasks.filter((task) => task.status === "IN_PROGRESS").length,
    todo: validTasks.filter((task) => task.status === "TODO").length,
    progress: total ? Math.round((completed / total) * 100) : null,
  };
}

function formatDeadline(deadline) {
  if (typeof deadline !== "string" || !deadline.trim()) {
    return "—";
  }

  const date = new Date(deadline);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
  }).format(date);
}

<<<<<<< HEAD
=======
function formatPeriod(team) {
  const period = team.period;
  const startDate = formatDeadline(period?.start_date);
  const endDate = formatDeadline(period?.end_date);
  return period?.name
    ? `${period.name} (${startDate} – ${endDate})`
    : `${startDate} – ${endDate}`;
}

function renderTeamInfo(teams) {
  const teamName = document.querySelector("[data-team-name]");
  const period = document.querySelector("[data-internship-period]");
  const supervisor = document.querySelector("[data-supervisor-name]");
  const note = document.querySelector("[data-team-source-note]");

  if (!Array.isArray(teams)) {
    throw new TypeError("Team data must be an array.");
  }
  if (teams.length === 0) {
    if (teamName) teamName.textContent = "Chưa được phân nhóm";
    if (period) period.textContent = "Chưa có dữ liệu";
    if (supervisor) supervisor.textContent = "Chưa có dữ liệu";
    if (note) note.textContent = "Bạn chưa được phân vào nhóm thực tập nào.";
    return;
  }

  const team = teams[0];
  if (
    team === null ||
    typeof team !== "object" ||
    typeof team.team_name !== "string" ||
    !team.period ||
    typeof team.period !== "object"
  ) {
    throw new TypeError("Team data is invalid.");
  }

  if (teamName) teamName.textContent = team.team_name;
  if (period) period.textContent = formatPeriod(team);
  if (supervisor) {
    supervisor.textContent =
      typeof team.supervisor?.full_name === "string"
        ? team.supervisor.full_name
        : "Chưa có dữ liệu";
  }
  if (note) note.textContent = "Thông tin nhóm trong kỳ thực tập gần nhất.";
}

>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
function createCell(content, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  cell.textContent = content;
  return cell;
}

function createTaskRow(task, index) {
  const row = document.createElement("tr");
  row.append(createCell(String(index + 1)));

  const title = createCell(task.title.trim(), "student-task-title");
<<<<<<< HEAD
  if (typeof task.description === "string" && task.description.trim()) {
    const description = document.createElement("div");
    description.className = "student-task-description muted";
    description.textContent = task.description.trim();
    title.append(description);
  }
  const detailButton = document.createElement("button");
  detailButton.className = "admin-row-action task-detail-button";
  detailButton.type = "button";
  detailButton.dataset.taskDetailId = String(task.id);
  detailButton.textContent = "Chi tiết";
  title.append(detailButton);
=======
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
  row.append(title, createCell(formatDeadline(task.deadline)));

  const priorityCell = document.createElement("td");
  const priority = Object.hasOwn(TASK_PRIORITIES, task.priority)
    ? TASK_PRIORITIES[task.priority]
    : null;
  if (priority) {
    const priorityLabel = document.createElement("span");
    priorityLabel.className = `student-priority ${priority.className}`;
    priorityLabel.textContent = priority.label;
    priorityCell.append(priorityLabel);
  } else {
    priorityCell.textContent = "—";
  }
  row.append(priorityCell);

  const statusCell = document.createElement("td");
  const status = document.createElement("span");
  status.className = `student-status student-status-${task.status.toLowerCase().replace("_", "-")}`;
  status.textContent = TASK_STATUS_LABELS[task.status];
  statusCell.append(status);
  row.append(statusCell, createTaskProgressCell(task));
  return row;
}

function createTaskProgressCell(task) {
  const cell = document.createElement("td");
  const progress = document.createElement("div");
  progress.className = "student-task-progress";

  let value = Number.isFinite(task.progress) && task.progress >= 0 && task.progress <= 100
    ? Math.round(task.progress)
    : null;
  if (value === null && task.status === "TODO") {
    value = 0;
  } else if (value === null && task.status === "DONE") {
    value = 100;
  }

  if (value === null) {
    progress.textContent = "—";
  } else {
    const track = document.createElement("span");
    track.className = "student-task-progress-track";
    const fill = document.createElement("span");
    fill.style.width = `${value}%`;
    track.append(fill);
    progress.append(track, document.createTextNode(`${value}%`));
  }

  cell.append(progress);
  return cell;
}

function renderTaskState(state, message) {
  const taskRows = document.querySelector("[data-task-rows]");
  if (!(taskRows instanceof HTMLTableSectionElement)) {
    return;
  }

  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.className = "student-state-cell";
  cell.colSpan = 6;

  const stateMessage = document.createElement("div");
  stateMessage.className = "student-state";
  stateMessage.dataset.state = state;
  stateMessage.dataset.taskState = "";
  stateMessage.setAttribute("role", state === "error" ? "alert" : "status");
  stateMessage.textContent = message;
  cell.append(stateMessage);
  row.append(cell);
  taskRows.replaceChildren(row);
  taskRows.setAttribute("aria-busy", String(state === "loading"));
}

export function showTaskDashboardError() {
  renderTaskState("error", "Không thể tải dữ liệu công việc. Vui lòng thử lại sau.");
}

<<<<<<< HEAD
function renderStudentProfile(user) {
  const profile = document.querySelector("[data-student-profile]");
  if (!(profile instanceof HTMLElement)) {
    return;
  }

  const details = [];
  if (typeof user.full_name === "string" && user.full_name.trim()) {
    details.push(`Họ tên: ${user.full_name.trim()}`);
  }
  if (typeof user.email === "string" && user.email.trim()) {
    details.push(`Email: ${user.email.trim()}`);
  }
  if (Number.isInteger(user.id)) {
    details.push(`Mã tài khoản: ${user.id}`);
  }
  if (typeof user.role === "string" && user.role) {
    details.push(`Vai trò: ${USER_ROLE_LABELS[user.role] || user.role}`);
  }
  if (typeof user.is_active === "boolean") {
    details.push(`Trạng thái: ${user.is_active ? "Đang hoạt động" : "Đã khóa"}`);
  }

  profile.textContent = details.length
    ? details.join(" · ")
    : "API không trả về thông tin hồ sơ.";
}

=======
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
export function renderTaskDashboard(tasks) {
  const metrics = calculateTaskMetrics(tasks);
  const taskRows = document.querySelector("[data-task-rows]");
  if (!(taskRows instanceof HTMLTableSectionElement)) {
    return;
  }

  const metricValues = {
    "[data-task-total]": metrics.total,
    "[data-task-done]": metrics.completed,
    "[data-task-in-progress]": metrics.inProgress,
    "[data-task-todo]": metrics.todo,
  };
  for (const [selector, value] of Object.entries(metricValues)) {
    const element = document.querySelector(selector);
    if (element) {
      element.textContent = String(value);
    }
  }
  const totalNote = document.querySelector("[data-task-total-note]");
  if (totalNote) {
    totalNote.textContent = "Chỉ gồm TODO, IN_PROGRESS và DONE.";
  }

  const progressValue = document.querySelector("[data-task-progress-value]");
  const progressBar = document.querySelector("[data-task-progress-bar]");
  const progressFill = document.querySelector("[data-task-progress-fill]");
  const progressNote = document.querySelector("[data-task-progress-note]");
  if (
    progressValue instanceof HTMLElement &&
    progressBar instanceof HTMLElement &&
    progressFill instanceof HTMLElement &&
    progressNote instanceof HTMLElement
  ) {
    if (metrics.progress === null) {
      progressValue.textContent = "—";
      progressBar.hidden = true;
      progressBar.removeAttribute("aria-valuenow");
      progressBar.setAttribute("aria-valuetext", "Chưa có công việc hợp lệ");
      progressNote.textContent = "Chưa có công việc hợp lệ để tính tiến độ.";
    } else {
      progressValue.textContent = `${metrics.progress}%`;
      progressBar.hidden = false;
      progressBar.setAttribute("aria-valuenow", String(metrics.progress));
      progressBar.setAttribute("aria-valuetext", `${metrics.progress}% hoàn thành`);
      progressFill.style.width = `${metrics.progress}%`;
      progressNote.textContent =
        `${metrics.completed} / ${metrics.total} công việc hợp lệ đã hoàn thành.`;
    }
  }

  if (metrics.tasks.length === 0) {
    renderTaskState("empty", "Chưa có công việc hợp lệ để hiển thị.");
    return;
  }

  taskRows.replaceChildren(...metrics.tasks.map(createTaskRow));
  taskRows.setAttribute("aria-busy", "false");
}

<<<<<<< HEAD
export function initializeStudentDashboard(user) {
  const studentName = document.querySelector("[data-student-name]");
  const mainContent = document.querySelector("#main-content");

  renderStudentProfile(user);
=======
export async function initializeStudentDashboard(user) {
  const studentName = document.querySelector("[data-student-name]");
  const mainContent = document.querySelector("#main-content");

>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
  if (studentName) {
    studentName.textContent =
      typeof user.full_name === "string" && user.full_name.trim()
        ? user.full_name.trim()
        : "sinh viên";
  }
  if (mainContent instanceof HTMLElement) {
    mainContent.setAttribute("aria-busy", "false");
  }

<<<<<<< HEAD
=======
  try {
    renderTeamInfo(await apiRequest("teams/me"));
  } catch (error) {
    console.error("Student team summary could not be loaded.", error);
    for (const selector of [
      "[data-team-name]",
      "[data-internship-period]",
      "[data-supervisor-name]",
    ]) {
      const element = document.querySelector(selector);
      if (element) {
        element.textContent = "Không thể tải dữ liệu";
      }
    }
    const note = document.querySelector("[data-team-source-note]");
    if (note) {
      note.textContent = "Không thể tải thông tin nhóm. Vui lòng thử lại sau.";
    }
  }

>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
  renderTaskState(
    "unavailable",
    "API công việc chưa được cung cấp. Các số liệu sẽ hiển thị khi backend hỗ trợ.",
  );
}
