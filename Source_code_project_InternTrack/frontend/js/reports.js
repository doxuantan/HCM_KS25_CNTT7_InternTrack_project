import { apiRequest, downloadAttachment } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeNotifications } from "./notifications.js";
import { initializeSharedUi, showToast } from "./ui.js";

let reports = [];

function state(message, isError = false) {
  const body = document.querySelector("[data-report-rows]");
  if (!(body instanceof HTMLTableSectionElement)) return;
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 5;
  cell.className = "admin-table-state";
  cell.textContent = message;
  cell.setAttribute("role", isError ? "alert" : "status");
  row.append(cell);
  body.replaceChildren(row);
}

function statusName(value) {
  return ({
    DRAFT: "Bản nháp",
    SUBMITTED: "Đã nộp",
    REVIEWING: "Đang xem xét",
    REVISION_REQUIRED: "Yêu cầu chỉnh sửa",
    APPROVED: "Đã duyệt",
  })[value] || value;
}

function renderReports() {
  const body = document.querySelector("[data-report-rows]");
  if (!(body instanceof HTMLTableSectionElement)) return;
  if (!reports.length) {
    state("Bạn chưa có báo cáo thực tập.");
    return;
  }
  body.replaceChildren(...reports.map((report) => {
    const row = document.createElement("tr");
    const title = document.createElement("td");
    title.textContent = report.title;
    for (const review of report.reviews || []) {
      const comment = document.createElement("p");
      comment.className = "muted";
      comment.textContent = `${statusName(review.status)}: ${review.content}`;
      title.append(comment);
    }
    const status = document.createElement("td");
    status.textContent = statusName(report.status);
    const actions = document.createElement("td");
    const attachmentButton = document.createElement("button");
    attachmentButton.type = "button";
    attachmentButton.className = "admin-row-action";
    attachmentButton.dataset.reportAttachments = String(report.id);
    attachmentButton.textContent = "Tệp báo cáo";
    actions.append(attachmentButton);
    if (report.status === "DRAFT" || report.status === "REVISION_REQUIRED") {
      const file = document.createElement("input");
      file.type = "file";
      file.accept = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      file.setAttribute("aria-label", `Tệp báo cáo ${report.title}`);
      file.dataset.reportFile = "";
      const submit = document.createElement("button");
      submit.type = "button";
      submit.className = "admin-row-action";
      submit.dataset.uploadAndSubmit = String(report.id);
      submit.textContent = "Tải tệp và nộp";
      actions.append(file, submit);
    }
    row.append(
      title,
      makeCell(report.report_type === "FINAL" ? "Cuối kỳ" : "Hàng tuần"),
      makeCell(report.submitted_at ? new Date(report.submitted_at).toLocaleString("vi-VN") : "Chưa nộp"),
      status,
      actions,
    );
    return row;
  }));
}

function makeCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value || "—";
  return cell;
}

async function loadReports() {
  state("Đang tải báo cáo...");
  try {
    reports = await apiRequest("reports");
    if (!Array.isArray(reports)) throw new Error("API báo cáo trả về dữ liệu không hợp lệ.");
    renderReports();
  } catch (error) {
    reports = [];
    state(`Không thể tải báo cáo: ${error.message}`, true);
  }
}

async function loadOptions() {
  const [periods, teams] = await Promise.all([
    apiRequest("internship-periods"),
    apiRequest("teams"),
  ]);
  const periodSelect = document.querySelector("[data-report-period]");
  const teamSelect = document.querySelector("[data-report-team]");
  if (periodSelect instanceof HTMLSelectElement) {
    periodSelect.replaceChildren(new Option("Chọn kỳ thực tập", ""));
    for (const period of periods) {
      periodSelect.add(new Option(period.name, String(period.id)));
    }
  }
  if (teamSelect instanceof HTMLSelectElement) {
    teamSelect.replaceChildren(new Option("Báo cáo cá nhân", ""));
    for (const team of teams) {
      teamSelect.add(new Option(team.team_name, String(team.id)));
    }
  }
}

async function createAndSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!(form instanceof HTMLFormElement)) return;
  const file = form.elements.report_file.files[0];
  if (!file) {
    showToast("Chọn tệp PDF hoặc DOCX trước khi tạo báo cáo.", { kind: "error" });
    return;
  }
  const teamId = Number(form.elements.team_id.value);
  let createdReport = null;
  try {
    createdReport = await apiRequest("reports", {
      method: "POST",
      body: {
        team_id: teamId || null,
        period_id: Number(form.elements.period_id.value),
        title: form.elements.title.value.trim(),
        report_type: form.elements.report_type.value,
      },
    });
    const uploadBody = new FormData();
    uploadBody.set("report_id", String(createdReport.id));
    uploadBody.set("file", file);
    await apiRequest("attachments/upload", { method: "POST", body: uploadBody });
    await apiRequest(`reports/${createdReport.id}/submit`, { method: "POST" });
    form.reset();
    showToast("Đã tải lên và nộp báo cáo.");
    await loadReports();
  } catch (error) {
    showToast(error.message, { kind: "error" });
    if (createdReport) form.reset();
    await loadReports();
  }
}

async function uploadAndSubmitExistingReport(reportId, file) {
  if (!file) {
    showToast("Chọn tệp PDF hoặc DOCX trước khi nộp.", { kind: "error" });
    return;
  }
  try {
    const body = new FormData();
    body.set("report_id", String(reportId));
    body.set("file", file);
    await apiRequest("attachments/upload", { method: "POST", body });
    await apiRequest(`reports/${reportId}/submit`, { method: "POST" });
    showToast("Đã nộp lại báo cáo.");
    await loadReports();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

document.querySelector("[data-report-form]")?.addEventListener("submit", (event) => void createAndSubmit(event));
document.querySelector("[data-report-rows]")?.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const submit = target?.closest("[data-upload-and-submit]");
  if (submit) {
    const file = submit.closest("tr")?.querySelector("[data-report-file]");
    void uploadAndSubmitExistingReport(
      Number(submit.dataset.uploadAndSubmit),
      file instanceof HTMLInputElement ? file.files[0] : null,
    );
    return;
  }
  const attachmentButton = target?.closest("[data-report-attachments]");
  if (!attachmentButton) return;
  const row = attachmentButton.closest("tr");
  const existing = row?.querySelector("[data-attachment-list]");
  if (existing) {
    existing.remove();
    return;
  }
  const list = document.createElement("div");
  list.dataset.attachmentList = "";
  list.textContent = "Đang tải tệp...";
  attachmentButton.closest("td")?.append(list);
  void apiRequest(`attachments?report_id=${encodeURIComponent(attachmentButton.dataset.reportAttachments)}`)
    .then((items) => {
      list.replaceChildren();
      if (!items.length) {
        list.textContent = "Chưa tải tệp báo cáo.";
        return;
      }
      for (const item of items) {
        const download = document.createElement("button");
        download.type = "button";
        download.className = "admin-row-action";
        download.textContent = item.file_name;
        download.addEventListener("click", () => {
          void downloadAttachment(item.id, item.file_name)
            .catch((error) => showToast(error.message, { kind: "error" }));
        });
        list.append(download);
      }
    })
    .catch((error) => {
      list.textContent = `Không tải được tệp: ${error.message}`;
    });
});

try {
  const user = await requireAuth();
  if (user) {
    await initializeSharedUi();
    await initializeNotifications();
    await loadOptions();
    await loadReports();
    document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
  }
} catch (error) {
  state(`Không thể khởi tạo trang báo cáo: ${error.message}`, true);
}