import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { confirmAction, initializeSharedUi, showToast } from "./ui.js";

const STATUS_LABELS = {
  UPCOMING: "Sắp diễn ra",
  ACTIVE: "Đang diễn ra",
  COMPLETED: "Đã hoàn thành",
};

let periods = [];
let currentUser = null;
const dialog = document.querySelector("[data-period-dialog]");
const form = document.querySelector("[data-period-form]");

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("vi-VN").format(date);
}

function stateRow(message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.className = "admin-table-state";
  cell.textContent = message;
  row.append(cell);
  return row;
}

function render() {
  const body = document.querySelector("[data-periods-rows]");
  const status = document.querySelector("[data-period-status-filter]")?.value || "";
  if (!body) return;
  const filtered = periods.filter((item) => !status || item.status === status);
  if (!filtered.length) {
    body.replaceChildren(stateRow(periods.length ? "Không có kỳ phù hợp." : "Chưa có kỳ thực tập."));
    return;
  }
  body.replaceChildren(...filtered.map((period) => {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.innerHTML = `<strong>${escapeHtml(period.name)}</strong><br><span class="muted">${escapeHtml(period.description || `ID ${period.id}`)}</span>`;
    row.append(name);
    for (const value of [formatDate(period.start_date), formatDate(period.end_date)]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    const statusCell = document.createElement("td");
    if (currentUser?.role === "ADMIN") {
      const select = document.createElement("select");
      select.className = "admin-inline-select";
      select.dataset.periodStatus = "";
      select.dataset.periodId = String(period.id);
      for (const [value, label] of Object.entries(STATUS_LABELS)) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        option.selected = value === period.status;
        select.append(option);
      }
      statusCell.append(select);
    } else {
      statusCell.textContent = STATUS_LABELS[period.status] || period.status;
    }
    const actions = document.createElement("td");
    actions.className = "admin-row-actions";
    for (const [label, action] of [
      ["Xem", "view"],
      ...(currentUser?.role === "ADMIN" ? [["Sửa", "edit"]] : []),
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "admin-row-action";
      button.dataset.periodAction = action;
      button.dataset.periodId = String(period.id);
      button.textContent = label;
      actions.append(button);
    }
    row.append(statusCell, actions);
    return row;
  }));
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value);
  return node.innerHTML;
}

function openPeriodDetail(period) {
  const detailDialog = document.querySelector("[data-period-detail-dialog]");
  if (!(detailDialog instanceof HTMLDialogElement)) return;
  document.querySelector("[data-period-detail-title]").textContent = period.name || "Chi tiết đợt thực tập";
  const list = document.querySelector("[data-period-detail-list]");
  const items = [
    ["ID", period.id],
    ["Tên đợt", period.name],
    ["Mô tả", period.description],
    ["Ngày bắt đầu", formatDate(period.start_date)],
    ["Ngày kết thúc", formatDate(period.end_date)],
    ["Hạn nộp báo cáo", period.report_deadline ? formatDate(period.report_deadline) : "—"],
    ["Trạng thái", STATUS_LABELS[period.status] || period.status],
  ];
  list.replaceChildren(...items.map(([label, value]) => {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value == null || value === "" ? "—" : String(value);
    item.append(term, detail);
    return item;
  }));
  detailDialog.showModal();
}

function openDialog(period = null) {
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  form.reset();
  form.dataset.periodId = period ? String(period.id) : "";
  document.querySelector("[data-period-dialog-title]").textContent = period ? "Chỉnh sửa kỳ thực tập" : "Thêm kỳ thực tập";
  document.querySelector("#period-status").closest("label").hidden = Boolean(period);
  if (period) {
    form.elements.name.value = period.name || "";
    form.elements.description.value = period.description || "";
    form.elements.start_date.value = period.start_date || "";
    form.elements.end_date.value = period.end_date || "";
  }
  dialog.showModal();
}

async function load() {
  const body = document.querySelector("[data-periods-rows]");
  if (body) body.replaceChildren(stateRow("Đang tải kỳ thực tập..."));
  try {
    periods = await apiRequest("internship-periods");
    render();
  } catch (error) {
    if (body) body.replaceChildren(stateRow(error.message));
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!(form instanceof HTMLFormElement)) return;
  const periodId = form.dataset.periodId;
  const reportDeadline = form.elements.report_deadline.value;
  const body = {
    name: form.elements.name.value.trim(),
    description: form.elements.description.value.trim() || null,
    start_date: form.elements.start_date.value,
    end_date: form.elements.end_date.value,
    report_deadline: reportDeadline ? `${reportDeadline}:00` : null,
  };
  if (!periodId) body.status = form.elements.status.value;
  if (body.end_date < body.start_date) {
    showToast("Ngày kết thúc không được trước ngày bắt đầu.", { kind: "error" });
    return;
  }
  try {
    await apiRequest(periodId ? `internship-periods/${periodId}` : "internship-periods", {
      method: periodId ? "PUT" : "POST",
      body,
    });
    dialog.close();
    showToast(periodId ? "Đã cập nhật kỳ thực tập." : "Đã tạo kỳ thực tập.");
    await load();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

document.querySelector("[data-create-period]")?.addEventListener("click", () => openDialog());
document.querySelector("[data-period-status-filter]")?.addEventListener("change", render);
document.querySelector("[data-periods-rows]")?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-period-action]") : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const period = periods.find((item) => String(item.id) === button.dataset.periodId);
  if (period && button.dataset.periodAction === "view") openPeriodDetail(period);
  if (period && button.dataset.periodAction === "edit") openDialog(period);
});
document.querySelector("[data-periods-rows]")?.addEventListener("change", async (event) => {
  const select = event.target;
  if (!(select instanceof HTMLSelectElement) || !select.matches("[data-period-status]")) return;
  try {
    await apiRequest(`internship-periods/${select.dataset.periodId}/status`, {
      method: "PATCH",
      body: { status: select.value },
    });
    showToast("Đã cập nhật trạng thái kỳ thực tập.");
    await load();
  } catch (error) {
    showToast(error.message, { kind: "error" });
    await load();
  }
});
document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => dialog?.close());
});
document.querySelectorAll("[data-close-period-detail]").forEach((button) => {
  button.addEventListener("click", () => document.querySelector("[data-period-detail-dialog]")?.close());
});

currentUser = await requireAuth();
if (currentUser?.role !== "ADMIN") {
  document.querySelector("[data-create-period]")?.setAttribute("hidden", "");
}
await initializeSharedUi();
await load();
