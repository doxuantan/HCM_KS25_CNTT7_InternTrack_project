import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { confirmAction, initializeSharedUi, showToast } from "./ui.js";

let teams = [];
let periods = [];
let users = [];
let activeTeamId = null;

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
  [periods, users] = await Promise.all([
    apiRequest("internship-periods"),
    apiRequest("users?skip=0&limit=100"),
  ]);
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
  }
  if (supervisorSelect) {
    const supervisors = users.filter((user) => user.role === "SUPERVISOR" && user.lecturer_profile);
    supervisorSelect.replaceChildren(...supervisors.map((user) => {
      const option = document.createElement("option");
      option.value = String(user.lecturer_profile.id);
      option.textContent = `${user.full_name} (${user.lecturer_profile.lecturer_code})`;
      return option;
    }));
  }
}

function stateRow(message, columns = 5) {
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
  const filtered = teams.filter((team) => `${team.team_name} ${team.team_code}`.toLocaleLowerCase("vi-VN").includes(term));
  if (!filtered.length) {
    body.replaceChildren(stateRow(teams.length ? "Không tìm thấy nhóm phù hợp." : "Chưa có nhóm thực tập."));
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
    const statusCell = document.createElement("td");
    statusCell.textContent = { ACTIVE: "Đang hoạt động", INACTIVE: "Không hoạt động", COMPLETED: "Đã hoàn thành" }[team.status] || team.status;
    const actions = document.createElement("td");
    actions.className = "admin-row-actions";
    for (const [label, action] of [
      ["Sửa", "edit"],
      ["Thành viên", "member"],
      ["Nhóm trưởng", "leader"],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "admin-row-action";
      button.dataset.teamAction = action;
      button.dataset.teamId = String(team.id);
      button.textContent = label;
      actions.append(button);
    }
    row.append(name, periodCell, supervisorCell, statusCell, actions);
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
  [teams, periods, users] = await Promise.all([
    apiRequest("teams"),
    apiRequest("internship-periods"),
    apiRequest("users?skip=0&limit=100"),
  ]);
  fillTeamFormOptions();
  renderTeams();
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
  document.querySelector("[data-student-team-name]").textContent = team.team_name;
  document.querySelector("[data-student-team-code]").textContent = team.team_code;
  document.querySelector("[data-student-team-supervisor]").textContent =
    team.supervisor_name ? `${team.supervisor_name}${team.supervisor_code ? ` (${team.supervisor_code})` : ""}` : `ID ${team.supervisor_id}`;
  const members = await apiRequest(`teams/${team.id}/members`);
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
  document.querySelector("#main-content").setAttribute("aria-busy", "false");
}

async function openMemberDialog(teamId) {
  activeTeamId = teamId;
  const members = await apiRequest(`teams/${teamId}/members`);
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

async function openLeaderDialog(teamId) {
  activeTeamId = teamId;
  const members = await apiRequest(`teams/${teamId}/members`);
  const select = document.querySelector("#leader-student");
  select.replaceChildren(...members.map((member) => {
    const option = document.createElement("option");
    option.value = String(member.student_id);
    option.textContent = member.student_name ? `${member.student_name} (${member.student_code || member.student_id})` : `Sinh viên ID ${member.student_id}`;
    option.selected = member.is_leader;
    return option;
  }));
  document.querySelector("[data-leader-dialog]").showModal();
}

document.querySelector("[data-team-search]")?.addEventListener("input", renderTeams);
document.querySelector("[data-create-team]")?.addEventListener("click", () => openTeamDialog());

document.querySelector("[data-team-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const teamId = form.dataset.teamId;
  const body = {
    period_id: Number(form.elements.period_id.value),
    supervisor_id: Number(form.elements.supervisor_id.value),
    team_name: form.elements.team_name.value.trim(),
    team_code: form.elements.team_code.value.trim(),
    description: form.elements.description.value.trim() || null,
  };
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
  try {
    await apiRequest(`teams/${activeTeamId}/members`, {
      method: "POST",
      body: { student_id: Number(form.elements.student_id.value) },
    });

    document.querySelector("[data-member-list]")?.addEventListener("click", async (event) => {
      const button = event.target instanceof Element ? event.target.closest("[data-remove-member-id]") : null;
      if (!(button instanceof HTMLButtonElement) || !(await confirmAction({
        title: "Xóa thành viên",
        message: "Xóa sinh viên khỏi nhóm thực tập?",
        confirmLabel: "Xóa thành viên",
        destructive: true,
      }))) return;
      try {
        await apiRequest(`teams/${activeTeamId}/members/${button.dataset.removeMemberId}`, { method: "DELETE" });
        showToast("Đã xóa thành viên khỏi nhóm.");
        document.querySelector("[data-member-dialog]")?.close();
        await openMemberDialog(activeTeamId);
      } catch (error) {
        showToast(error.message, { kind: "error" });
      }
    });
    document.querySelector("[data-member-dialog]").close();
    showToast("Đã thêm thành viên.");
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-leader-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
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

document.querySelector("[data-teams-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-team-action]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const teamId = Number(button.dataset.teamId);
  const team = teams.find((item) => item.id === teamId);
  if (button.dataset.teamAction === "edit" && team) openTeamDialog(team);
  if (button.dataset.teamAction === "member") {
    void openMemberDialog(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
  if (button.dataset.teamAction === "leader") {
    void openLeaderDialog(teamId).catch((error) => showToast(error.message, { kind: "error" }));
  }
});

for (const [dialogSelector, closeSelector] of [
  ["[data-team-dialog]", "[data-close-team-dialog]"],
  ["[data-member-dialog]", "[data-close-member-dialog]"],
  ["[data-leader-dialog]", "[data-close-leader-dialog]"],
]) {
  const dialog = document.querySelector(dialogSelector);
  document.querySelectorAll(closeSelector).forEach((button) => button.addEventListener("click", () => dialog?.close()));
}

await requireAuth();
await initializeSharedUi();
if (isStudentView()) {
  await loadStudentTeam();
} else {
  await loadAdminTeams();
}
