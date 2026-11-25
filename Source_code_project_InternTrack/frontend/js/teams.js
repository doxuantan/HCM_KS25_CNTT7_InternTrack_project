import { apiRequest } from "./api.js";
import { logout, requireAuth } from "./auth.js";
import { confirmAction, initializeSharedUi, showToast } from "./ui.js";

let teams = [];
let periods = [];
let users = [];
let activeTeamId = null;
let currentUser = null;
const teamMembersCache = new Map();
let studentTeam = null;
let studentTeamMembers = [];
let leaderTasks = [];

function isStudentView() {
  return document.body.dataset.teamView === "student";
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

async function loadUsersAndReferences() {
  if (isStudentView()) return;
  try {
    periods = await apiRequest("internship-periods");
  } catch (error) {
    periods = [];
    showToast(error.message, { kind: "error" });
  }
  try {
    users = currentUser?.role === "ADMIN"
      ? await apiRequest("users?skip=0&limit=100")
      : [];
  } catch (error) {
    users = [];
    showToast(error.message, { kind: "error" });
  }
  fillTeamFormOptions();
}

function fillTeamFormOptions() {
  const periodSelect = document.querySelector("#team-period");
  const supervisorSelect = document.querySelector("#team-supervisor");
  if (periodSelect) {
    periodSelect.replaceChildren(...periods.map((period) => {
      const option = document.createElement("option");
      option.value = String(period.id);
      option.textContent = period.name;
      return option;
    }));
    periodSelect.disabled = !periods.length;
    if (!periods.length) {
      periodSelect.replaceChildren(new Option("Chưa có kỳ thực tập", "", true, true));
    }
  }
  if (supervisorSelect) {
    if (currentUser?.role === "SUPERVISOR") {
      supervisorSelect.closest("label")?.setAttribute("hidden", "");
      supervisorSelect.required = false;
      return;
    }
    supervisorSelect.closest("label")?.removeAttribute("hidden");
    supervisorSelect.required = true;
    const supervisors = users.filter((user) => user.role === "SUPERVISOR" && user.lecturer_profile);
    supervisorSelect.replaceChildren(...supervisors.map((user) => {
      const option = document.createElement("option");
      option.value = String(user.lecturer_profile.id);
      option.textContent = `${user.full_name} (${user.lecturer_profile.lecturer_code})`;
      return option;
    }));
    supervisorSelect.disabled = !supervisors.length;
    if (!supervisors.length) {
      supervisorSelect.replaceChildren(new Option("Chưa có giảng viên", "", true, true));
    }
  }
}

function stateRow(message, columns = 6) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = columns;
  cell.className = "admin-table-state";
  cell.textContent = message;
  row.append(cell);
  return row;
}

function renderTeams() {
  const body = document.querySelector("[data-teams-rows]");
  if (!body) return;
  const term = document.querySelector("[data-team-search]")?.value.trim().toLocaleLowerCase("vi-VN") || "";
  const periodId = document.querySelector("[data-team-period-filter]")?.value || "";
  const status = document.querySelector("[data-team-status-filter]")?.value || "";
  const filtered = teams.filter((team) =>
    `${team.team_name} ${team.team_code}`.toLocaleLowerCase("vi-VN").includes(term)
    && (!periodId || String(team.period_id) === periodId)
    && (!status || team.status === status));
  if (!filtered.length) {
    body.replaceChildren(stateRow(teams.length ? "Không tìm thấy nhóm phù hợp." : "Chưa có nhóm thực tập.", 6));
    return;
  }
  body.replaceChildren(...filtered.map((team) => {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.innerHTML = `<strong>${escapeHtml(team.team_name)}</strong><br><span class="muted">${escapeHtml(team.team_code)}</span>`;
    const period = periods.find((item) => item.id === team.period_id);
    const supervisor = users.find((item) => item.role === "SUPERVISOR" && item.lecturer_profile?.id === team.supervisor_id);
    const periodCell = document.createElement("td");
    periodCell.textContent = period?.name || `ID ${team.period_id}`;
    const supervisorCell = document.createElement("td");
    supervisorCell.textContent = team.supervisor_name || supervisor?.full_name || `ID ${team.supervisor_id}`;
    const memberCell = document.createElement("td");
    const memberCount = teamMembersCache.get(team.id)?.length;
    memberCell.innerHTML = `<span class="team-member-count">${typeof memberCount === "number" ? memberCount : "—"} thành viên</span>`;
    const statusCell = document.createElement("td");
    const statusText = { ACTIVE: "Đang hoạt động", INACTIVE: "Không hoạt động", COMPLETED: "Đã hoàn thành" }[team.status] || team.status;
    statusCell.innerHTML = `<span class="team-status team-status-${escapeHtml(team.status.toLowerCase())}">${escapeHtml(statusText)}</span>`;
    const actions = document.createElement("td");
    actions.className = "admin-row-actions";
    const actionItems = [["Chi tiết", "detail"]];
    if (currentUser?.role === "ADMIN" || currentUser?.role === "SUPERVISOR") {
      actionItems.push(["Sửa", "edit"], ["Thành viên", "member"]);
    }
    if (currentUser?.role === "ADMIN" || currentUser?.role === "SUPERVISOR") {
      actionItems.push(["Nhóm trưởng", "leader"]);
    }
    if (currentUser?.role === "ADMIN") {
      actionItems.push(["Giảng viên", "supervisor"]);
      actionItems.push(["Xóa", "delete"]);
    }
    for (const [label, action] of actionItems) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "admin-row-action";
      if (action === "delete") button.classList.add("admin-row-action-danger");
      button.dataset.teamAction = action;
      button.dataset.teamId = String(team.id);
      button.textContent = label;
      actions.append(button);
    }
    row.append(name, periodCell, supervisorCell, memberCell, statusCell, actions);
    return row;
  }));
}

function openTeamDialog(team = null) {
  const dialog = document.querySelector("[data-team-dialog]");
  const form = document.querySelector("[data-team-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  form.reset();
  form.dataset.teamId = team ? String(team.id) : "";
  document.querySelector("[data-team-dialog-title]").textContent = team ? "Chỉnh sửa nhóm" : "Tạo nhóm";
  fillTeamFormOptions();
  if (team) {
    form.elements.period_id.value = String(team.period_id);
    form.elements.supervisor_id.value = String(team.supervisor_id);
    form.elements.team_name.value = team.team_name;
    form.elements.team_code.value = team.team_code;
    form.elements.description.value = team.description || "";
    form.elements.status.value = team.status;
  }
  dialog.showModal();
}

async function loadAdminTeams() {
  const body = document.querySelector("[data-teams-rows]");
  if (body) body.replaceChildren(stateRow("Đang tải nhóm thực tập..."));
  teams = await apiRequest("teams");
  await loadUsersAndReferences();
  fillTeamFormOptions();
  fillTeamFilters();
  teamMembersCache.clear();
  await Promise.all(teams.map(async (team) => {
    try {
      teamMembersCache.set(team.id, await apiRequest(`teams/${team.id}/members`));
    } catch (error) {
      teamMembersCache.set(team.id, []);
    }
  }));
  renderTeamStats();
  renderTeams();
}

function fillTeamFilters() {
  const filter = document.querySelector("[data-team-period-filter]");
  if (filter instanceof HTMLSelectElement) {
    const selected = filter.value;
    filter.replaceChildren(
      new Option("Tất cả", ""),
      ...periods.map((period) => new Option(period.name, String(period.id))),
    );
    if ([...filter.options].some((option) => option.value === selected)) {
      filter.value = selected;
    }
  }
}

function renderTeamStats() {
  const total = teams.length;
  const active = teams.filter((team) => team.status === "ACTIVE").length;
  const members = Array.from(teamMembersCache.values()).reduce((sum, items) => sum + items.length, 0);
  const withoutSupervisor = teams.filter((team) => !team.supervisor_id).length;
  document.querySelector("[data-team-stat-total]")?.replaceChildren(document.createTextNode(String(total)));
  document.querySelector("[data-team-stat-active]")?.replaceChildren(document.createTextNode(String(active)));
  document.querySelector("[data-team-stat-members]")?.replaceChildren(document.createTextNode(String(members)));
  document.querySelector("[data-team-stat-supervisor]")?.replaceChildren(document.createTextNode(String(withoutSupervisor)));
}

async function loadStudentTeam() {
  const studentTeams = await apiRequest("teams");
  if (!Array.isArray(studentTeams) || !studentTeams.length) {
    document.querySelector("[data-student-team-name]").textContent = "Chưa tham gia nhóm";
    document.querySelector("[data-student-team-code]").textContent = "—";
    document.querySelector("[data-student-team-leader]").textContent = "—";
    document.querySelector("[data-student-team-supervisor]").textContent = "—";
    document.querySelector("[data-student-team-members]").replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "Sinh viên chưa tham gia nhóm trong kỳ hiện tại.";
    row.append(cell);
    document.querySelector("[data-student-team-members]").append(row);
    return;
  }
  const team = studentTeams[0];
  studentTeam = team;
  activeTeamId = team.id;
  document.querySelector("[data-student-team-name]").textContent = team.team_name;
  document.querySelector("[data-student-team-code]").textContent = team.team_code;
  document.querySelector("[data-student-team-supervisor]").textContent =
    team.supervisor_name ? `${team.supervisor_name}${team.supervisor_code ? ` (${team.supervisor_code})` : ""}` : `ID ${team.supervisor_id}`;
  const members = await apiRequest(`teams/${team.id}/members`);
  studentTeamMembers = members;
  const body = document.querySelector("[data-student-team-members]");
  if (!members.length) {
    body.replaceChildren(stateRow("Chưa có thành viên.", 3));
  } else {
    body.replaceChildren(...members.map((member) => {
      const row = document.createElement("tr");
      for (const value of [
        member.student_name || `Sinh viên ID ${member.student_id}`,
        member.student_code || "—",
        member.is_leader ? "Nhóm trưởng" : "Thành viên",
      ]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      if (member.is_leader) {
        document.querySelector("[data-student-team-leader]").textContent =
          member.student_name ? `${member.student_name}${member.student_code ? ` (${member.student_code})` : ""}` : `ID ${member.student_id}`;
      }
      return row;
    }));
  }
  const studentProfileId = currentUser?.student_profile?.id;
  const currentUserId = currentUser?.id;
  const isLeader = members.some((member) =>
    member.is_leader
      && (
        member.user_id === currentUserId
        || (studentProfileId != null && member.student_id === studentProfileId)
      ));
  const panel = document.querySelector("[data-leader-task-panel]");
  const pageEntry = document.querySelector("[data-create-leader-task-entry]");
  if (isLeader) {
    panel?.removeAttribute("hidden");
    pageEntry?.removeAttribute("hidden");
    pageEntry?.removeAttribute("disabled");
    await loadLeaderTasks();
  } else {
    panel?.setAttribute("hidden", "");
    pageEntry?.setAttribute("hidden", "");
  }
  document.querySelector("#main-content").setAttribute("aria-busy", "false");
}

async function openMemberDialog(teamId) {
  activeTeamId = teamId;
  const members = await apiRequest(`teams/${teamId}/members`);
  teamMembersCache.set(teamId, members);
  const existing = new Set(members.map((member) => member.student_id));
  const studentSelect = document.querySelector("#member-student");
  const students = users.filter((user) => user.role === "STUDENT" && user.student_profile);
  studentSelect.replaceChildren(...students
    .filter((user) => !existing.has(user.student_profile.id))
    .map((user) => {
      const option = document.createElement("option");
      option.value = String(user.student_profile.id);
      option.textContent = `${user.full_name} (${user.student_profile.student_code})`;
      return option;
    }));
  if (studentSelect.options.length === 0) {
    studentSelect.replaceChildren(new Option("Không còn sinh viên phù hợp", "", true, true));
  }
  const idField = document.querySelector("[data-member-id-field]");
  const fallbackInput = document.querySelector("#member-student-id");
  if (currentUser?.role === "SUPERVISOR") {
    studentSelect.closest("label")?.setAttribute("hidden", "");
    studentSelect.required = false;
    idField?.removeAttribute("hidden");
    fallbackInput.required = true;
  } else {
    studentSelect.closest("label")?.removeAttribute("hidden");
    studentSelect.required = true;
    idField?.setAttribute("hidden", "");
    fallbackInput.required = false;
  }
  const memberList = document.querySelector("[data-member-list]");
  if (memberList) {
    memberList.replaceChildren(...members.map((member) => {
      const item = document.createElement("div");
      item.className = "team-member-item";
      const name = document.createElement("span");
      name.textContent = `${member.student_name || `Sinh viên ID ${member.student_id}`}${member.is_leader ? " · Nhóm trưởng" : ""}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "admin-row-action admin-row-action-danger";
      remove.dataset.removeMemberId = String(member.student_id);
      remove.textContent = "Xóa";
      remove.disabled = member.is_leader;
      item.append(name, remove);
      return item;
    }));
  }
  document.querySelector("[data-member-dialog]").showModal();
}

async function openTeamDetail(teamId) {
  const team = teams.find((item) => item.id === teamId);
  if (!team) return;
  const dialog = document.querySelector("[data-team-detail-dialog]");
  const members = await apiRequest(`teams/${teamId}/members`);
  const period = periods.find((item) => item.id === team.period_id);
  document.querySelector("[data-team-detail-title]").textContent = team.team_name;
  const supervisor = users.find((item) => item.role === "SUPERVISOR" && item.lecturer_profile?.id === team.supervisor_id);
  const detailItems = [
    ["Mã nhóm", team.team_code],
    ["Kỳ thực tập", period?.name || `ID ${team.period_id}`],
    ["Giảng viên hướng dẫn", team.supervisor_name || supervisor?.full_name || `ID ${team.supervisor_id}`],
    ["Trạng thái", { ACTIVE: "Đang hoạt động", INACTIVE: "Không hoạt động", COMPLETED: "Đã hoàn thành" }[team.status] || team.status],
    ["Mô tả", team.description],
  ];
  document.querySelector("[data-team-detail-list]").replaceChildren(...detailItems.map(([label, value]) => {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value == null || value === "" ? "—" : String(value);
    item.append(term, detail);
    return item;
  }));
  const memberList = document.querySelector("[data-team-detail-members]");
  memberList.replaceChildren(...members.map((member) => {
    const item = document.createElement("div");
    item.className = "team-member-item";
    item.textContent = `${member.student_name || `Sinh viên ID ${member.student_id}`} — ${member.is_leader ? "Nhóm trưởng" : "Thành viên"}`;
    return item;
  }));
  dialog?.showModal();
}

async function openLeaderDialog(teamId) {
  activeTeamId = teamId;
  const members = await apiRequest(`teams/${teamId}/members`);
  const select = document.querySelector("#leader-student");
  if (!members.length) {
    select.replaceChildren(new Option("Nhóm chưa có thành viên", "", true, true));
    select.disabled = true;
  } else {
    select.disabled = false;
    select.replaceChildren(...members.map((member) => {
      const option = document.createElement("option");
      option.value = String(member.student_id);
      option.textContent = member.student_name ? `${member.student_name} (${member.student_code || member.student_id})` : `Sinh viên ID ${member.student_id}`;
      option.selected = member.is_leader;
      return option;
    }));
  }
  document.querySelector("[data-leader-dialog]").showModal();
}

function formatTaskDeadline(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: "Asia/Ho_Chi_Minh",
    }).format(date);
}

async function loadLeaderTasks() {
  if (!studentTeam) return;
  const body = document.querySelector("[data-leader-task-rows]");
  try {
    const payload = await apiRequest(`tasks?team=${studentTeam.id}&limit=100&sort=created_desc`);
    leaderTasks = Array.isArray(payload) ? payload : payload.items || [];
  } catch (error) {
    leaderTasks = [];
  }
  if (!leaderTasks.length) {
    body?.replaceChildren(stateRow("Nhóm chưa có task.", 6));
    return;
  }
  const statusLabels = {
    TODO: "Chưa bắt đầu",
    IN_PROGRESS: "Đang thực hiện",
    REVIEW: "Chờ duyệt",
    DONE: "Hoàn thành",
    CANCELLED: "Đã hủy",
  };
  const priorityLabels = { LOW: "Thấp", MEDIUM: "Trung bình", HIGH: "Cao" };
  body?.replaceChildren(...leaderTasks.map((task) => {
    const row = document.createElement("tr");
    const assignees = task.assignments?.map((item) =>
      item.student_name || item.student_code || `Sinh viên #${item.student_id}`) || [];
    [
      task.title,
      assignees.join(", ") || "Chưa giao",
      formatTaskDeadline(task.deadline),
      priorityLabels[task.priority] || task.priority,
      statusLabels[task.status] || task.status,
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    const actions = document.createElement("td");
    const detail = document.createElement("button");
    detail.type = "button";
    detail.className = "admin-row-action";
    detail.dataset.leaderTaskDetail = String(task.id);
    detail.textContent = "Chi tiết";
    actions.append(detail);
    row.append(actions);
    return row;
  }));
}

function openLeaderTaskDialog() {
  const dialog = document.querySelector("[data-leader-task-dialog]");
  const form = document.querySelector("[data-leader-task-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  form.reset();
  const today = new Date();
  form.elements.start_date.value =
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  form.elements.student_ids.replaceChildren(...studentTeamMembers
    .map((member) => new Option(
      member.student_name ? `${member.student_name} (${member.student_code || member.student_id})` : `Sinh viên #${member.student_id}`,
      String(member.student_id),
    )));
  dialog.showModal();
}

async function openLeaderTaskDetail(taskId) {
  const task = await apiRequest(`tasks/${taskId}`);
  const dialog = document.querySelector("[data-leader-task-detail]");
  if (!(dialog instanceof HTMLDialogElement)) return;
  document.querySelector("[data-leader-task-detail-title]").textContent = task.title;
  document.querySelector("[data-leader-task-detail-status]").textContent =
    ({ TODO: "Chưa bắt đầu", IN_PROGRESS: "Đang thực hiện", REVIEW: "Chờ duyệt", DONE: "Hoàn thành", CANCELLED: "Đã hủy" })[task.status] || task.status;
  document.querySelector("[data-leader-task-detail-deadline]").textContent = formatTaskDeadline(task.deadline);
  document.querySelector("[data-leader-task-detail-priority]").textContent =
    ({ LOW: "Thấp", MEDIUM: "Trung bình", HIGH: "Cao" })[task.priority] || task.priority;
  document.querySelector("[data-leader-task-detail-assignees]").textContent =
    task.assignments?.length
      ? task.assignments.map((item) => item.student_name || item.student_code || `Sinh viên #${item.student_id}`).join(", ")
      : "Chưa giao";
  document.querySelector("[data-leader-task-detail-description]").textContent =
    task.description || "Không có mô tả.";
  dialog.showModal();
}

async function openSupervisorDialog(teamId) {
  activeTeamId = teamId;
  const team = teams.find((item) => item.id === teamId);
  const select = document.querySelector("#team-supervisor-change");
  const supervisors = users.filter((user) => user.role === "SUPERVISOR" && user.lecturer_profile);
  if (!supervisors.length) {
    select.replaceChildren(new Option("Chưa có giảng viên", "", true, true));
    select.disabled = true;
  } else {
    select.disabled = false;
    select.replaceChildren(...supervisors.map((user) => {
      const option = document.createElement("option");
      option.value = String(user.lecturer_profile.id);
      option.textContent = `${user.full_name} (${user.lecturer_profile.lecturer_code})`;
      option.selected = user.lecturer_profile.id === team?.supervisor_id;
      return option;
    }));
  }
  document.querySelector("[data-supervisor-dialog]").showModal();
}

document.querySelector("[data-team-search]")?.addEventListener("input", renderTeams);
document.querySelector("[data-team-period-filter]")?.addEventListener("change", renderTeams);
document.querySelector("[data-team-status-filter]")?.addEventListener("change", renderTeams);
document.querySelector("[data-create-team]")?.addEventListener("click", () => openTeamDialog());

document.querySelector("[data-team-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const teamId = form.dataset.teamId;
  if (!form.elements.period_id.value || form.elements.period_id.disabled) {
    showToast("Vui lòng tạo hoặc chọn kỳ thực tập.", { kind: "error" });
    return;
  }
  if (currentUser?.role === "ADMIN" && (!form.elements.supervisor_id.value || form.elements.supervisor_id.disabled)) {
    showToast("Vui lòng chọn giảng viên hướng dẫn.", { kind: "error" });
    return;
  }
  const body = {
    period_id: Number(form.elements.period_id.value),
    team_name: form.elements.team_name.value.trim(),
    team_code: form.elements.team_code.value.trim(),
    description: form.elements.description.value.trim() || null,
  };
  if (currentUser?.role === "ADMIN") {
    body.supervisor_id = Number(form.elements.supervisor_id.value);
  }
  if (!teamId) body.status = form.elements.status.value;
  else body.status = form.elements.status.value;
  try {
    await apiRequest(teamId ? `teams/${teamId}` : "teams", {
      method: teamId ? "PUT" : "POST",
      body,
    });
    document.querySelector("[data-team-dialog]").close();
    showToast(teamId ? "Đã cập nhật nhóm." : "Đã tạo nhóm.");
    await loadAdminTeams();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-member-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const fallbackInput = form.elements.student_id_fallback;
  const studentId =
    currentUser?.role === "SUPERVISOR"
      ? Number(fallbackInput?.value)
      : Number(form.elements.student_id.value);
  if (!studentId) {
    showToast("Không còn sinh viên phù hợp để thêm.", { kind: "error" });
    return;
  }
  try {
    await apiRequest(`teams/${activeTeamId}/members`, {
      method: "POST",
      body: { student_id: studentId },
    });
    document.querySelector("[data-member-dialog]").close();
    showToast("Đã thêm thành viên.");
    await loadAdminTeams();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-member-list]")?.addEventListener("click", async (event) => {
  const button = event.target instanceof Element
    ? event.target.closest("[data-remove-member-id]")
    : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const confirmed = await confirmAction({
    title: "Xóa thành viên",
    message: "Xóa sinh viên khỏi nhóm thực tập?",
    confirmLabel: "Xóa thành viên",
    destructive: true,
  });
  if (!confirmed) return;
  try {
    await apiRequest(
      `teams/${activeTeamId}/members/${button.dataset.removeMemberId}`,
      { method: "DELETE" },
    );
    showToast("Đã xóa thành viên khỏi nhóm.");
    await loadAdminTeams();
    await openMemberDialog(activeTeamId);
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-leader-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.elements.student_id.value || form.elements.student_id.disabled) {
    showToast("Nhóm chưa có thành viên để chọn làm nhóm trưởng.", { kind: "error" });
    return;
  }
  try {
    await apiRequest(`teams/${activeTeamId}/leader`, {
      method: "PATCH",
      body: { student_id: Number(form.elements.student_id.value) },
    });
    document.querySelector("[data-leader-dialog]").close();
    showToast("Đã cập nhật nhóm trưởng.");
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-supervisor-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.elements.supervisor_id.value || form.elements.supervisor_id.disabled) {
    showToast("Không có giảng viên hướng dẫn để phân công.", { kind: "error" });
    return;
  }
  try {
    await apiRequest(`teams/${activeTeamId}/supervisor`, {
      method: "PATCH",
      body: { supervisor_id: Number(form.elements.supervisor_id.value) },
    });
    document.querySelector("[data-supervisor-dialog]").close();
    showToast("Đã cập nhật giảng viên hướng dẫn.");
    await loadAdminTeams();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-create-leader-task]")?.addEventListener("click", openLeaderTaskDialog);
document.querySelector("[data-create-leader-task-entry]")?.addEventListener("click", openLeaderTaskDialog);

document.querySelector("[data-leader-task-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!(form instanceof HTMLFormElement) || !studentTeam) return;
  const selectedIds = Array.from(form.elements.student_ids.selectedOptions)
    .map((option) => Number(option.value))
    .filter((id) => id > 0);
  if (!selectedIds.length) {
    showToast("Vui lòng chọn ít nhất một thành viên để giao task.", { kind: "error" });
    return;
  }
  const startDate = form.elements.start_date.value;
  const deadline = form.elements.deadline.value;
  if (!deadline || deadline.slice(0, 10) < startDate) {
    showToast("Deadline phải cùng hoặc sau ngày bắt đầu.", { kind: "error" });
    return;
  }
  if (new Date(deadline).getTime() <= Date.now()) {
    showToast("Deadline không được nằm trong quá khứ.", { kind: "error" });
    return;
  }
  try {
    const created = await apiRequest("tasks", {
      method: "POST",
      body: {
        team_id: studentTeam.id,
        title: form.elements.title.value.trim(),
        description: form.elements.description.value.trim() || null,
        task_type: "TEAM",
        priority: form.elements.priority.value,
        start_date: startDate,
        deadline,
      },
    });
    await apiRequest(`tasks/${created.id}/assign`, {
      method: "PUT",
      body: { student_ids: selectedIds },
    });
    document.querySelector("[data-leader-task-dialog]")?.close();
    form.reset();
    showToast("Đã tạo và phân công task.");
    await loadLeaderTasks();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-leader-task-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element
    ? event.target.closest("[data-leader-task-detail]")
    : null;
  if (!(button instanceof HTMLButtonElement)) return;
  void openLeaderTaskDetail(Number(button.dataset.leaderTaskDetail))
    .catch((error) => showToast(error.message, { kind: "error" }));
});

document.querySelector("[data-teams-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-team-action]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const teamId = Number(button.dataset.teamId);
  const team = teams.find((item) => item.id === teamId);
  if (button.dataset.teamAction === "detail") {
    void openTeamDetail(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
  if (button.dataset.teamAction === "edit" && team) openTeamDialog(team);
  if (button.dataset.teamAction === "member") {
    void openMemberDialog(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
  if (button.dataset.teamAction === "leader") {
    void openLeaderDialog(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
  if (button.dataset.teamAction === "supervisor") {
    void openSupervisorDialog(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
  if (button.dataset.teamAction === "delete" && team) {
    void (async () => {
      const confirmed = await confirmAction({
        title: "Xóa nhóm thực tập",
        message: `Bạn có chắc muốn xóa nhóm "${team.team_name}"? Nhóm có thành viên hoặc task sẽ không thể xóa.`,
        confirmLabel: "Xóa nhóm",
        destructive: true,
      });
      if (!confirmed) return;
      try {
        await apiRequest(`teams/${teamId}`, { method: "DELETE" });
        showToast("Đã xóa nhóm thực tập.");
        await loadAdminTeams();
      } catch (error) {
        showToast(error.message, { kind: "error" });
      }
    })();
  }
});

for (const [dialogSelector, closeSelector] of [
  ["[data-team-dialog]", "[data-close-team-dialog]"],
  ["[data-member-dialog]", "[data-close-member-dialog]"],
  ["[data-leader-dialog]", "[data-close-leader-dialog]"],
  ["[data-team-detail-dialog]", "[data-close-team-detail]"],
  ["[data-supervisor-dialog]", "[data-close-supervisor-dialog]"],
  ["[data-leader-task-dialog]", "[data-close-leader-task]"],
  ["[data-leader-task-detail]", "[data-close-leader-task-detail]"],
]) {
  const dialog = document.querySelector(dialogSelector);
  document.querySelectorAll(closeSelector).forEach((button) => button.addEventListener("click", () => dialog?.close()));
}

currentUser = await requireAuth();
if (currentUser?.role !== "ADMIN") {
  document.querySelector("[data-create-team]")?.setAttribute("hidden", "");
}
if (currentUser) {
  document.querySelectorAll("[data-team-user-name]").forEach((element) => {
    element.textContent = currentUser.full_name || "Người dùng";
  });
  document.querySelectorAll("[data-team-user-role]").forEach((element) => {
    element.textContent = currentUser.role;
  });
  const initials = (currentUser.full_name || currentUser.role || "IT")
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  document.querySelector("[data-team-user-initials]")?.replaceChildren(document.createTextNode(initials));
}
document.querySelectorAll("[data-logout]").forEach((button) => {
  button.addEventListener("click", logout);
});
document.querySelector("[data-team-refresh]")?.addEventListener("click", async () => {
  const button = document.querySelector("[data-team-refresh]");
  if (button instanceof HTMLButtonElement) {
    button.disabled = true;
    button.textContent = "Đang làm mới...";
  }
  try {
    await loadAdminTeams();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  } finally {
    if (button instanceof HTMLButtonElement) {
      button.disabled = false;
      button.textContent = "↻ Làm mới";
    }
  }
});
document.querySelector("[data-sidebar-toggle]")?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});
document.querySelector("[data-sidebar-backdrop]")?.addEventListener("click", () => {
  document.body.classList.remove("sidebar-open");
});
const accountToggle = document.querySelector("[data-account-toggle]");
const accountMenu = document.querySelector("[data-account-menu]");
accountToggle?.addEventListener("click", (event) => {
  event.stopPropagation();
  if (!(accountMenu instanceof HTMLElement)) return;
  const open = accountMenu.hidden;
  accountMenu.hidden = !open;
  accountToggle.setAttribute("aria-expanded", String(open));
});
document.addEventListener("click", (event) => {
  if (event.target instanceof Element && !event.target.closest("[data-account-menu-container]")) {
    if (accountMenu instanceof HTMLElement) accountMenu.hidden = true;
    accountToggle?.setAttribute("aria-expanded", "false");
  }
});
await initializeSharedUi();
if (isStudentView()) {
  await loadStudentTeam();
} else {
  try {
    await loadAdminTeams();
  } catch (error) {
    const body = document.querySelector("[data-teams-rows]");
    if (body) body.replaceChildren(stateRow(`Không tải được danh sách nhóm: ${error.message}`, 5));
  } finally {
    document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
  }
}
