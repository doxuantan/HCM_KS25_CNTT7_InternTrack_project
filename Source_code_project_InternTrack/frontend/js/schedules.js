import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeSharedUi, showToast, confirmAction } from "./ui.js";
import { initializeNotifications } from "./notifications.js";

let currentUser = null;
let schedules = [];
let teams = [];
let activeScheduleId = null;

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function toLocalInput(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
}

function teamName(teamId) {
  return teams.find((team) => String(team.id) === String(teamId))?.team_name || `Nhóm #${teamId}`;
}

function canManage() {
  return currentUser?.role === "ADMIN" || currentUser?.role === "SUPERVISOR";
}

async function loadSchedules() {
  const body = document.querySelector("[data-schedule-rows]");
  if (body instanceof HTMLElement) body.setAttribute("aria-busy", "true");
  try {
    [teams, schedules] = await Promise.all([
      apiRequest("teams"),
      apiRequest("schedules"),
    ]);
    const teamFilter = document.querySelector("[data-schedule-team-filter]");
    if (teamFilter instanceof HTMLSelectElement) {
      teamFilter.replaceChildren(
        new Option("Tất cả nhóm", ""),
        ...(Array.isArray(teams)
          ? teams.map((team) => new Option(team.team_name || `Nhóm #${team.id}`, String(team.id)))
          : [])
      );
    }
    renderSchedules();
  } catch (error) {
    if (body instanceof HTMLElement) {
      body.innerHTML = `<tr><td colspan="6" class="admin-table-state" role="alert">${escapeHtml(error.message)}</td></tr>`;
    }
  } finally {
    if (body instanceof HTMLElement) body.setAttribute("aria-busy", "false");
  }
}

function renderSchedules() {
  const body = document.querySelector("[data-schedule-rows]");
  if (!(body instanceof HTMLElement)) return;
  const teamId = document.querySelector("[data-schedule-team-filter]")?.value || "";
  const query = document.querySelector("[data-schedule-search]")?.value.trim().toLowerCase() || "";
  const filtered = schedules.filter((schedule) =>
    (!teamId || String(schedule.team_id) === teamId)
    && (!query || `${schedule.title} ${schedule.location || ""} ${schedule.description || ""}`.toLowerCase().includes(query))
  );
  if (!filtered.length) {
    body.innerHTML = '<tr><td colspan="6" class="admin-table-state">Không có lịch phù hợp.</td></tr>';
    return;
  }
  body.innerHTML = filtered.map((schedule) => `
    <tr>
      <td><strong>${escapeHtml(schedule.title)}</strong>${schedule.description ? `<br><span class="muted">${escapeHtml(schedule.description)}</span>` : ""}</td>
      <td>${escapeHtml(teamName(schedule.team_id))}</td>
      <td>${escapeHtml(formatDateTime(schedule.start_time))}</td>
      <td>${escapeHtml(formatDateTime(schedule.end_time))}</td>
      <td>${escapeHtml(schedule.location || "—")}</td>
      <td>
        <button class="admin-row-action" type="button" data-schedule-detail="${schedule.id}">Chi tiết</button>
        ${canManage() ? `<button class="admin-row-action" type="button" data-schedule-edit="${schedule.id}">Sửa</button><button class="admin-row-action" type="button" data-schedule-delete="${schedule.id}">Xóa</button>` : ""}
      </td>
    </tr>
  `).join("");
}

function fillTeamSelect(selectedTeamId = "") {
  const select = document.querySelector("[data-schedule-team]");
  if (!(select instanceof HTMLSelectElement)) return;
  select.replaceChildren(...teams.map((team) =>
    new Option(team.team_name || `Nhóm #${team.id}`, String(team.id))
  ));
  if (selectedTeamId) select.value = String(selectedTeamId);
}

function openCreate() {
  if (!canManage()) return;
  activeScheduleId = null;
  const dialog = document.querySelector("[data-schedule-dialog]");
  const form = document.querySelector("[data-schedule-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  form.reset();
  fillTeamSelect();
  document.querySelector("[data-schedule-dialog-title]").textContent = "Tạo lịch nhóm";
  dialog.showModal();
}

function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
}

function openDetail(schedule) {
  const dialog = document.querySelector("[data-schedule-detail-dialog]");
  if (!schedule || !(dialog instanceof HTMLDialogElement)) return;
  setText("[data-schedule-detail-title]", schedule.title);
  setText("[data-schedule-detail-team]", teamName(schedule.team_id));
  setText("[data-schedule-detail-start]", formatDateTime(schedule.start_time));
  setText("[data-schedule-detail-end]", formatDateTime(schedule.end_time));
  setText("[data-schedule-detail-location]", schedule.location || "—");
  setText("[data-schedule-detail-description]", schedule.description || "Không có mô tả.");
  dialog.showModal();
}

function openEdit(schedule) {
  if (!schedule || !canManage()) return;
  activeScheduleId = schedule.id;
  const dialog = document.querySelector("[data-schedule-dialog]");
  const form = document.querySelector("[data-schedule-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  fillTeamSelect(schedule.team_id);
  form.elements.title.value = schedule.title;
  form.elements.description.value = schedule.description || "";
  form.elements.location.value = schedule.location || "";
  form.elements.start_time.value = toLocalInput(schedule.start_time);
  form.elements.end_time.value = toLocalInput(schedule.end_time);
  document.querySelector("[data-schedule-dialog-title]").textContent = "Cập nhật lịch nhóm";
  dialog.showModal();
}

async function submitSchedule(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!(form instanceof HTMLFormElement)) return;
  const payload = {
    team_id: Number(form.elements.team_id.value),
    title: form.elements.title.value.trim(),
    description: form.elements.description.value.trim() || null,
    location: form.elements.location.value.trim() || null,
    start_time: form.elements.start_time.value,
    end_time: form.elements.end_time.value,
  };
  if (!payload.team_id || !payload.title || !payload.start_time || !payload.end_time) {
    showToast("Vui lòng nhập đầy đủ thông tin bắt buộc.", { kind: "error" });
    return;
  }
  try {
    if (activeScheduleId) {
      await apiRequest(`schedules/${activeScheduleId}`, { method: "PUT", body: payload });
      showToast("Đã cập nhật lịch.");
    } else {
      await apiRequest("schedules", { method: "POST", body: payload });
      showToast("Đã tạo lịch nhóm.");
    }
    document.querySelector("[data-schedule-dialog]")?.close();
    await loadSchedules();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

async function deleteSchedule(schedule) {
  const confirmed = await confirmAction({
    title: "Xóa lịch",
    message: `Bạn có chắc muốn xóa lịch "${schedule.title}"?`,
    confirmLabel: "Xóa lịch",
    destructive: true,
  });
  if (!confirmed) return;
  try {
    await apiRequest(`schedules/${schedule.id}`, { method: "DELETE" });
    showToast("Đã xóa lịch.");
    await loadSchedules();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

document.querySelector("[data-schedule-create]")?.addEventListener("click", openCreate);
document.querySelector("[data-schedule-form]")?.addEventListener("submit", submitSchedule);
document.querySelector("[data-schedule-team-filter]")?.addEventListener("change", renderSchedules);
document.querySelector("[data-schedule-search]")?.addEventListener("input", renderSchedules);
document.querySelector("[data-schedule-close]")?.addEventListener("click", () => document.querySelector("[data-schedule-dialog]")?.close());
document.querySelector("[data-schedule-detail-close]")?.addEventListener("click", () => document.querySelector("[data-schedule-detail-dialog]")?.close());
document.querySelector("[data-schedule-rows]")?.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const detail = target?.closest("[data-schedule-detail]");
  const edit = target?.closest("[data-schedule-edit]");
  const remove = target?.closest("[data-schedule-delete]");
  if (detail) openDetail(schedules.find((item) => String(item.id) === detail.dataset.scheduleDetail));
  if (edit) openEdit(schedules.find((item) => String(item.id) === edit.dataset.scheduleEdit));
  if (remove) {
    const schedule = schedules.find((item) => String(item.id) === remove.dataset.scheduleDelete);
    if (schedule) void deleteSchedule(schedule);
  }
});

currentUser = await requireAuth();
if (currentUser) {
  await initializeSharedUi();
  await initializeNotifications();
  const createButton = document.querySelector("[data-schedule-create]");
  if (createButton instanceof HTMLButtonElement) createButton.hidden = !canManage();
  await loadSchedules();
  document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
}