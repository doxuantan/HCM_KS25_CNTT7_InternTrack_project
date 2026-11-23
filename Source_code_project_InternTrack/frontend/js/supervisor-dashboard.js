import { apiRequest, downloadAttachment } from "./api.js";
import { requireAuth, logout } from "./auth.js";
import { confirmAction, initializeSharedUi, showToast } from "./ui.js";
import { initializeNotifications } from "./notifications.js";

let currentUser = null;
let teams = [];
let periods = [];
let tasks = [];
let teamProgress = [];
let activeReview = null;
let evaluations = [];
let evaluationCriteria = [];
let editingEvaluationId = null;

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = String(value ?? "");
  return node.innerHTML;
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function statusLabel(status) {
  const labels = {
    ACTIVE: "Đang hoạt động",
    INACTIVE: "Ngừng hoạt động",
    COMPLETED: "Hoàn thành",
    TODO: "Chưa làm",
    IN_PROGRESS: "Đang làm",
    REVIEW: "Chờ duyệt",
    DONE: "Hoàn thành",
    CANCELLED: "Đã hủy",
    DRAFT: "Bản nháp",
    SUBMITTED: "Đã nộp",
    REVIEWING: "Đang duyệt",
    REVIEWED: "Đã nhận xét",
    REVISION_REQUIRED: "Yêu cầu sửa",
    APPROVED: "Đã duyệt",
  };
  return labels[status] || status || "—";
}

function statusBadge(status) {
  const safeStatus = String(status || "UNKNOWN").toLowerCase().replaceAll("_", "-");
  return `<span class="supervisor-status supervisor-status-${escapeHtml(safeStatus)}">${escapeHtml(statusLabel(status))}</span>`;
}

function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
}

function setTexts(selector, value) {
  document.querySelectorAll(selector).forEach((element) => {
    element.textContent = value;
  });
}

function stateRow(container, message, columns) {
  container.innerHTML = `<tr><td class="admin-table-state" colspan="${columns}">${escapeHtml(message)}</td></tr>`;
}

async function loadDashboard() {
  const [periodResult, teamResult, taskResult, overviewResult] = await Promise.allSettled([
    apiRequest("internship-periods"),
    apiRequest("teams"),
    apiRequest("tasks"),
    apiRequest("progress/overview"),
  ]);

  periods = periodResult.status === "fulfilled" ? normalizeList(periodResult.value) : [];
  teams = teamResult.status === "fulfilled" ? normalizeList(teamResult.value) : [];
  tasks = taskResult.status === "fulfilled" ? normalizeList(taskResult.value) : [];

  const overview = overviewResult.status === "fulfilled" ? overviewResult.value : null;
  setText("[data-stat-periods]", String(periods.length));
  setText("[data-stat-teams]", String(teams.length));
  setText("[data-stat-progress]", overview ? `${Number(overview.progress).toFixed(1)}%` : "—");
  setText("[data-stat-overdue]", String(overview?.overdue_tasks ?? 0));
  setText(
    "[data-stat-progress-note]",
    overview
      ? `${overview.completed_tasks}/${overview.total_tasks} task hoàn thành`
      : "Không tải được dữ liệu tiến độ",
  );

  const teamFilter = document.querySelector("[data-dashboard-team]");
  if (teamFilter instanceof HTMLSelectElement) {
    teamFilter.replaceChildren(
      new Option("Tất cả nhóm", ""),
      ...teams.map((team) => new Option(team.team_name || `Nhóm #${team.id}`, String(team.id))),
    );
  }

  renderPeriods();
  await renderTeamsAndProgress();
  renderUpcoming(overview?.upcoming_tasks || []);
  await Promise.all([
    renderDiaries(),
    renderReports(),
    renderEvaluations(),
    renderNotifications(),
  ]);
  document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
}

function renderPeriods() {
  const body = document.querySelector("[data-period-rows]");
  if (!body) return;
  if (!periods.length) {
    stateRow(body, "Chưa có kỳ thực tập thuộc phạm vi.", 4);
  } else {
    body.innerHTML = periods.map((period) => `
      <tr>
        <td><strong>${escapeHtml(period.name)}</strong></td>
        <td>${escapeHtml(formatDate(period.start_date))} – ${escapeHtml(formatDate(period.end_date))}</td>
        <td>${statusBadge(period.status)}</td>
        <td>${escapeHtml(period.description || "Không có mô tả")}</td>
      </tr>
    `).join("");
  }

  const container = document.querySelector("[data-overview-periods]");
  if (container) {
    container.innerHTML = periods.length
      ? periods.slice(0, 5).map((period) => `
        <div class="supervisor-list-item">
          <div><strong>${escapeHtml(period.name)}</strong>${statusBadge(period.status)}</div>
          <time>${escapeHtml(formatDate(period.start_date))}</time>
        </div>
      `).join("")
      : '<p class="muted" style="padding:16px">Chưa có kỳ thực tập.</p>';
  }
}

async function renderTeamsAndProgress() {
  const teamBody = document.querySelector("[data-team-rows]");
  const progressGrid = document.querySelector("[data-progress-grid]");
  if (!teams.length) {
    if (teamBody) stateRow(teamBody, "Chưa có nhóm sinh viên thuộc phạm vi.", 5);
    if (progressGrid) progressGrid.innerHTML = '<p class="muted">Chưa có dữ liệu nhóm.</p>';
    return;
  }

  const results = await Promise.all(
    teams.map((team) =>
      apiRequest(`progress/team/${team.id}`)
        .then((data) => data)
        .catch(() => null),
    ),
  );
  teamProgress = results.filter(Boolean);
  const studentFilter = document.querySelector("[data-diary-student]");
  if (studentFilter instanceof HTMLSelectElement) {
    const members = new Map();
    teamProgress.forEach((team) => {
      (team.members || []).forEach((member) => members.set(member.student_id, member));
    });
    studentFilter.replaceChildren(
      new Option("Tất cả sinh viên", ""),
      ...Array.from(members.values()).map((member) =>
        new Option(member.student_name || `Sinh viên #${member.student_id}`, String(member.student_id))),
    );
  }

  if (teamBody) {
    teamBody.innerHTML = teamProgress.map((progress) => `
      <tr data-team-progress-row="${progress.team_id}">
        <td><strong>${escapeHtml(progress.team_name)}</strong></td>
        <td>${progress.members?.length || 0}</td>
        <td><strong>${Number(progress.progress).toFixed(1)}%</strong></td>
        <td>${progress.completed_tasks}/${progress.total_tasks}</td>
        <td><button class="admin-row-action" type="button" data-progress-team="${progress.team_id}">Chi tiết</button></td>
      </tr>
    `).join("");
  }

  if (progressGrid) {
    progressGrid.innerHTML = teamProgress.map((progress) => `
      <article class="panel admin-panel supervisor-team-card" data-team-progress-card="${progress.team_id}">
        <h2>${escapeHtml(progress.team_name)}</h2>
        <div class="supervisor-progress-track" aria-label="Tiến độ ${escapeHtml(progress.team_name)}"><span style="width:${Number(progress.progress)}%"></span></div>
        <p><strong>${Number(progress.progress).toFixed(1)}%</strong> · ${progress.completed_tasks}/${progress.total_tasks} task hoàn thành</p>
        ${progress.members.map((member) => `
          <button class="supervisor-member-row" type="button" data-member-progress="${member.student_id}">
            <div><strong>${escapeHtml(member.student_name || `Sinh viên #${member.student_id}`)}</strong><span>${escapeHtml(member.student_code || "")}</span></div>
            <strong>${Number(member.progress).toFixed(1)}%</strong>
          </button>
        `).join("") || '<p class="muted">Chưa có thành viên.</p>'}
      </article>
    `).join("") || '<p class="muted">Không tải được tiến độ các nhóm.</p>';
  }
}

function renderUpcoming(upcoming) {
  const container = document.querySelector("[data-overview-upcoming]");
  if (!container) return;
  if (!upcoming.length) {
    container.innerHTML = '<p class="muted" style="padding:16px">Không có task sắp đến hạn.</p>';
    return;
  }
  container.innerHTML = upcoming.slice(0, 10).map((task) => `
    <div class="supervisor-list-item">
      <div><strong>${escapeHtml(task.title)}</strong>${statusBadge(task.status)}</div>
      <time>${escapeHtml(formatDate(task.deadline))}</time>
    </div>
  `).join("");
}

async function renderDiaries() {
  const body = document.querySelector("[data-diary-rows]");
  if (!body) return;
  try {
    const params = new URLSearchParams();
    const studentId = document.querySelector("[data-diary-student]")?.value;
    const workDate = document.querySelector("[data-diary-date]")?.value;
    const diaryStatus = document.querySelector("[data-diary-status]")?.value;
    if (studentId) params.set("student_id", studentId);
    if (workDate) params.set("work_date", workDate);
    if (diaryStatus) params.set("status", diaryStatus);
    const query = params.size ? `?${params}` : "";
    const diaries = normalizeList(await apiRequest(`diaries${query}`));
    if (!diaries.length) {
      stateRow(body, "Chưa có nhật ký thực tập.", 5);
      return;
    }
    body.innerHTML = diaries.map((diary) => `
      <tr>
        <td><strong>${escapeHtml(diary.student_name || `Sinh viên #${diary.student_id}`)}</strong><br><span class="muted">${escapeHtml(diary.student_code || "")}</span></td>
        <td>${escapeHtml(formatDate(diary.work_date))}</td>
        <td>${escapeHtml(diary.work_content)}${(diary.reviews || []).map((review) => `<p class="muted">${escapeHtml(statusLabel(review.status))}: ${escapeHtml(review.content)}</p>`).join("")}</td>
        <td>${statusBadge(diary.status)}</td>
        <td>${diary.status === "SUBMITTED" ? `<button class="admin-row-action" type="button" data-diary-review="${diary.id}" data-diary-title="${escapeHtml(diary.student_name || "Nhật ký")}">Nhận xét</button>` : "—"}</td>
      </tr>
    `).join("");
  } catch (error) {
    stateRow(body, error.status === 404 ? "API nhật ký chưa có dữ liệu." : `Không tải được nhật ký: ${error.message}`, 5);
  }
}

async function renderReports() {
  const body = document.querySelector("[data-report-rows]");
  if (!body) return;
  try {
    const reports = normalizeList(await apiRequest("reports"));
    if (!reports.length) {
      stateRow(body, "Chưa có báo cáo thực tập.", 5);
      return;
    }
    body.innerHTML = reports.map((report) => `
      <tr>
        <td><strong>${escapeHtml(report.title)}</strong>${(report.reviews || []).map((review) => `<p class="muted">${escapeHtml(statusLabel(review.status))}: ${escapeHtml(review.content)}</p>`).join("")}</td>
        <td>${escapeHtml(report.owner_name || "—")}</td>
        <td>${escapeHtml(report.report_type)}</td>
        <td>${statusBadge(report.status)}</td>
        <td>${report.file_url ? `<button class="admin-row-action" type="button" data-report-attachments="${report.id}">Tệp</button>` : ""} ${["SUBMITTED", "REVIEWING"].includes(report.status) ? `<button class="admin-row-action" type="button" data-report-review="${report.id}" data-report-title="${escapeHtml(report.title)}">Nhận xét</button>` : "—"}</td>
      </tr>
    `).join("");
  } catch (error) {
    stateRow(body, `Không tải được báo cáo: ${error.message}`, 5);
  }
}

async function renderEvaluations() {
  const body = document.querySelector("[data-evaluation-rows]");
  if (!body) return;
  try {
    evaluations = normalizeList(await apiRequest("evaluations"));
    if (!evaluations.length) {
      stateRow(body, "Chưa có phiếu đánh giá.", 5);
      return;
    }
    body.innerHTML = evaluations.map((evaluation) => {
      const student = teamProgress.flatMap((team) => team.members || []).find((member) => member.student_id === evaluation.student_id);
      const details = (evaluation.details || []).map((detail) => `${escapeHtml(detail.criteria_name || `Tiêu chí #${detail.criteria_id}`)}: ${detail.score}`).join("<br>");
      const actions = evaluation.is_published
        ? "Đã khóa"
        : `<button class="admin-row-action" type="button" data-edit-evaluation="${evaluation.id}">Sửa điểm</button><button class="admin-row-action" type="button" data-publish-evaluation="${evaluation.id}">Công bố</button><button class="admin-row-action" type="button" data-delete-evaluation="${evaluation.id}">Xóa</button>`;
      return `<tr><td>${escapeHtml(student?.student_name || (evaluation.team_id ? `Nhóm #${evaluation.team_id}` : `Sinh viên #${evaluation.student_id}`))}<p class="muted">${details || "Chưa nhập điểm theo tiêu chí"}</p></td><td>#${evaluation.period_id}</td><td>${evaluation.total_score ?? "—"}</td><td>${evaluation.is_published ? "Đã công bố" : "Chưa công bố"}</td><td>${escapeHtml(evaluation.comment || "—")}</td><td>${actions}</td></tr>`;
    }).join("");
  } catch (error) {
    stateRow(body, `Không tải được đánh giá: ${error.message}`, 5);
  }
}

async function renderNotifications() {
  const container = document.querySelector("[data-notification-list]");
  if (!container) return;
  try {
    const notifications = normalizeList(await apiRequest("notifications"));
    if (!notifications.length) {
      container.innerHTML = '<p class="muted" style="padding:16px">Chưa có thông báo.</p>';
      return;
    }
    container.innerHTML = notifications.map((notification) => `
      <div class="supervisor-list-item ${notification.is_read ? "" : "supervisor-notification-unread"}">
        <div><strong>${escapeHtml(notification.title)}</strong><span>${escapeHtml(notification.content)}</span></div>
        ${notification.is_read ? "" : `<button class="admin-row-action" type="button" data-read-notification="${notification.id}">Đánh dấu đã đọc</button>`}
      </div>
    `).join("");
  } catch (error) {
    container.innerHTML = `<p class="muted" style="padding:16px">Không tải được thông báo: ${escapeHtml(error.message)}</p>`;
  }
}

function openReview(kind, id, title) {
  activeReview = { kind, id };
  setText("[data-review-title]", `${kind === "diary" ? "Duyệt nhật ký" : "Duyệt báo cáo"} — ${title}`);
  const form = document.querySelector("[data-review-form]");
  if (form instanceof HTMLFormElement) form.reset();
  document.querySelector("[data-review-dialog]")?.showModal();
}

async function submitReview(reviewStatus) {
  if (!activeReview) return;
  const form = document.querySelector("[data-review-form]");
  if (!(form instanceof HTMLFormElement)) return;
  const content = form.elements.content.value.trim();
  if (!content) {
    showToast("Vui lòng nhập nhận xét.", { kind: "error" });
    return;
  }
  try {
    if (activeReview.kind === "diary") {
      await apiRequest(`diaries/${activeReview.id}/review`, {
        method: "POST",
        body: { status: reviewStatus === "APPROVED" ? "REVIEWED" : "REVISION_REQUIRED", content },
      });
      await renderDiaries();
    } else {
      await apiRequest(`reports/${activeReview.id}/review`, {
        method: "POST",
        body: { status: reviewStatus === "APPROVED" ? "APPROVED" : "REVISION_REQUIRED", content },
      });
      await renderReports();
    }
    document.querySelector("[data-review-dialog]")?.close();
    showToast("Đã lưu kết quả duyệt.");
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

async function openEvaluationDialog(evaluation = null) {
  const dialog = document.querySelector("[data-evaluation-dialog]");
  const form = document.querySelector("[data-evaluation-form]");
  if (!(dialog instanceof HTMLDialogElement) || !(form instanceof HTMLFormElement)) return;
  const evaluationId = evaluation?.id ?? null;
  const members = new Map();
  teamProgress.forEach((team) => {
    (team.members || []).forEach((member) => members.set(member.student_id, member));
  });
  form.elements.student_id.replaceChildren(
    ...Array.from(members.values()).map((member) => new Option(member.student_name || `Sinh viên #${member.student_id}`, String(member.student_id))),
  );
  form.elements.period_id.replaceChildren(
    ...periods.map((period) => new Option(period.name, String(period.id))),
  );
  try {
    evaluationCriteria = normalizeList(await apiRequest("evaluations/criteria"));
  } catch (error) {
    showToast(`Không tải được tiêu chí đánh giá: ${error.message}`, { kind: "error" });
    return;
  }
  const criteriaContainer = form.querySelector("[data-evaluation-criteria]");
  if (criteriaContainer) {
    criteriaContainer.replaceChildren(...evaluationCriteria.map((criteria) => {
      const field = document.createElement("label");
      field.className = "form-field";
      const title = document.createElement("span");
      title.className = "form-label";
      title.textContent = `${criteria.name} (trọng số ${criteria.weight})`;
      const input = document.createElement("input");
      input.className = "form-control";
      input.type = "number";
      input.min = "0";
      input.max = "999.99";
      input.step = "0.01";
      input.name = `score_${criteria.id}`;
      const detail = evaluation?.details?.find((item) => item.criteria_id === criteria.id);
      input.value = detail?.score ?? "";
      const comment = document.createElement("textarea");
      comment.className = "form-control";
      comment.name = `criteria_comment_${criteria.id}`;
      comment.maxLength = 2000;
      comment.rows = 2;
      comment.placeholder = "Nhận xét tiêu chí (không bắt buộc)";
      comment.value = detail?.comment || "";
      field.append(title, input, comment);
      return field;
    }));
  }
  editingEvaluationId = evaluationId;
  form.elements.student_id.value = evaluation?.student_id ? String(evaluation.student_id) : "";
  form.elements.period_id.value = evaluation?.period_id ? String(evaluation.period_id) : "";
  form.elements.comment.value = evaluation?.comment || "";
  setText("[data-evaluation-title]", evaluationId ? "Cập nhật điểm đánh giá" : "Tạo đánh giá sinh viên");
  const submitButton = form.querySelector('button[type="submit"]');
  if (submitButton) submitButton.textContent = evaluationId ? "Cập nhật đánh giá" : "Lưu đánh giá";
  dialog.showModal();
}

document.querySelectorAll("[data-supervisor-view]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const view = link.dataset.supervisorView;
    document.querySelectorAll("[data-supervisor-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.supervisorPanel !== view;
    });
    document.querySelectorAll("[data-supervisor-view]").forEach((item) => item.classList.toggle("is-active", item === link));
    setText("[data-supervisor-page-title]", link.textContent.trim());
    history.replaceState(null, "", `#${view}`);
    document.body.classList.remove("sidebar-open");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});

const accountToggle = document.querySelector("[data-account-toggle]");
const accountMenu = document.querySelector("[data-account-menu]");
accountToggle?.addEventListener("click", (event) => {
  event.stopPropagation();
  if (!(accountMenu instanceof HTMLElement)) return;
  const willOpen = accountMenu.hidden;
  accountMenu.hidden = !willOpen;
  accountToggle.setAttribute("aria-expanded", String(willOpen));
});
document.addEventListener("click", (event) => {
  if (event.target instanceof Element && !event.target.closest(".account-menu-container")) {
    if (accountMenu instanceof HTMLElement) accountMenu.hidden = true;
    accountToggle?.setAttribute("aria-expanded", "false");
  }
});

document.querySelectorAll("[data-close-review], [data-close-evaluation]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog")?.close());
});
document.querySelector("[data-close-member-progress]")?.addEventListener("click", () => {
  document.querySelector("[data-member-progress-dialog]")?.close();
});
document.querySelector("[data-review-approved]")?.addEventListener("click", () => void submitReview("APPROVED"));
document.querySelector("[data-review-revision]")?.addEventListener("click", () => void submitReview("REVISION_REQUIRED"));

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const memberButton = target?.closest("[data-member-progress]");
  if (memberButton) {
    const studentId = Number(memberButton.dataset.memberProgress);
    const dialog = document.querySelector("[data-member-progress-dialog]");
    const body = document.querySelector("[data-member-progress-body]");
    if (dialog instanceof HTMLDialogElement) {
      if (body instanceof HTMLElement) body.textContent = "Đang tải...";
      dialog.showModal();
      void apiRequest(`progress/member/${studentId}`)
        .then((progress) => {
          setText("[data-member-progress-title]", progress.student_name || `Sinh viên #${progress.student_id}`);
          if (body instanceof HTMLElement) {
            body.innerHTML = `
              <p><strong>Mã sinh viên:</strong> ${escapeHtml(progress.student_code || "—")}</p>
              <p><strong>Tiến độ:</strong> ${Number(progress.progress).toFixed(1)}%</p>
              <p><strong>Tổng task:</strong> ${progress.total_tasks} · <strong>Hoàn thành:</strong> ${progress.completed_tasks} · <strong>Đang làm:</strong> ${progress.in_progress_tasks} · <strong>Quá hạn:</strong> ${progress.overdue_tasks}</p>
            `;
          }
        })
        .catch((error) => {
          if (body instanceof HTMLElement) body.textContent = error.message;
        });
    }
  }
  const teamButton = target?.closest("[data-progress-team]");
  if (teamButton) {
    const progressLink = document.querySelector('[data-supervisor-view="progress"]');
    progressLink?.click();
  }
  const diaryButton = target?.closest("[data-diary-review]");
  if (diaryButton) openReview("diary", Number(diaryButton.dataset.diaryReview), diaryButton.dataset.diaryTitle);
  const reportButton = target?.closest("[data-report-review]");
  if (reportButton) openReview("report", Number(reportButton.dataset.reportReview), reportButton.dataset.reportTitle);
  const attachmentButton = target?.closest("[data-report-attachments]");
  if (attachmentButton) {
    const reportId = Number(attachmentButton.dataset.reportAttachments);
    void apiRequest(`attachments?report_id=${reportId}`)
      .then(async (items) => {
        if (!items.length) {
          showToast("Báo cáo chưa có tệp đính kèm.", { kind: "error" });
          return;
        }
        await downloadAttachment(items[items.length - 1].id, items[items.length - 1].file_name);
      })
      .catch((error) => showToast(error.message, { kind: "error" }));
  }
  const editEvaluation = target?.closest("[data-edit-evaluation]");
  if (editEvaluation) {
    const evaluation = evaluations.find((item) => item.id === Number(editEvaluation.dataset.editEvaluation));
    if (evaluation) void openEvaluationDialog(evaluation);
  }
  const publishEvaluation = target?.closest("[data-publish-evaluation]");
  if (publishEvaluation) {
    void apiRequest(`evaluations/${publishEvaluation.dataset.publishEvaluation}/publish`, { method: "POST" })
      .then(async () => {
        showToast("Đã công bố phiếu đánh giá và gửi thông báo.");
        await renderEvaluations();
      })
      .catch((error) => showToast(error.message, { kind: "error" }));
  }
  const deleteEvaluation = target?.closest("[data-delete-evaluation]");
  if (deleteEvaluation) {
    void confirmAction({
      title: "Xóa phiếu đánh giá",
      message: "Bạn có chắc muốn xóa phiếu đánh giá chưa công bố này?",
      confirmLabel: "Xóa phiếu",
      destructive: true,
    }).then(async (confirmed) => {
      if (!confirmed) return;
      try {
        await apiRequest(`evaluations/${deleteEvaluation.dataset.deleteEvaluation}`, { method: "DELETE" });
        showToast("Đã xóa phiếu đánh giá.");
        await renderEvaluations();
      } catch (error) {
        showToast(error.message, { kind: "error" });
      }
    });
  }
  const notificationButton = target?.closest("[data-read-notification]");
  if (notificationButton) {
    void apiRequest(`notifications/${notificationButton.dataset.readNotification}/read`, { method: "PATCH" })
      .then(() => renderNotifications())
      .catch((error) => showToast(error.message, { kind: "error" }));
  }
});

document.querySelector("[data-open-evaluation]")?.addEventListener("click", () => void openEvaluationDialog());
document.querySelector("[data-evaluation-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const details = evaluationCriteria.flatMap((criteria) => {
      const score = form.elements.namedItem(`score_${criteria.id}`)?.value;
      if (score === undefined || score === "") return [];
      const comment = form.elements.namedItem(`criteria_comment_${criteria.id}`)?.value.trim();
      return [{
        criteria_id: criteria.id,
        score: Number(score),
        comment: comment || null,
      }];
    });
    await apiRequest(editingEvaluationId ? `evaluations/${editingEvaluationId}` : "evaluations", {
      method: editingEvaluationId ? "PUT" : "POST",
      body: {
        student_id: Number(form.elements.student_id.value),
        period_id: Number(form.elements.period_id.value),
        comment: form.elements.comment.value.trim() || null,
        is_published: false,
        details,
      },
    });
    document.querySelector("[data-evaluation-dialog]")?.close();
    showToast(editingEvaluationId ? "Đã cập nhật đánh giá." : "Đã lưu đánh giá.");
    editingEvaluationId = null;
    await renderEvaluations();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
});

["[data-diary-student]", "[data-diary-date]", "[data-diary-status]"].forEach((selector) => {
  document.querySelector(selector)?.addEventListener("change", () => void renderDiaries());
});
document.querySelector("[data-diary-clear-filters]")?.addEventListener("click", () => {
  ["[data-diary-student]", "[data-diary-date]", "[data-diary-status]"].forEach((selector) => {
    const control = document.querySelector(selector);
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) control.value = "";
  });
  void renderDiaries();
});

document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", logout));
document.querySelector("[data-supervisor-refresh]")?.addEventListener("click", () => {
  const button = document.querySelector("[data-supervisor-refresh]");
  if (button instanceof HTMLButtonElement) {
    button.disabled = true;
    button.textContent = "Đang làm mới...";
  }
  void loadDashboard().finally(() => {
    if (button instanceof HTMLButtonElement) {
      button.disabled = false;
      button.textContent = "Làm mới dữ liệu";
    }
  });
});

function applyDashboardFilters() {
  const teamId = document.querySelector("[data-dashboard-team]")?.value || "";
  const status = document.querySelector("[data-dashboard-status]")?.value || "";
  const from = document.querySelector("[data-dashboard-from]")?.value || "";
  const to = document.querySelector("[data-dashboard-to]")?.value || "";

  document.querySelectorAll("[data-team-progress-row], [data-team-progress-card]").forEach((element) => {
    const elementTeamId = element.dataset.teamProgressRow || element.dataset.teamProgressCard;
    element.hidden = Boolean(teamId && elementTeamId !== teamId);
  });

  const filtered = tasks.filter((task) => {
    const deadline = task.deadline ? new Date(task.deadline) : null;
    const fromOk = !from || (deadline && deadline >= new Date(`${from}T00:00:00`));
    const toOk = !to || (deadline && deadline <= new Date(`${to}T23:59:59`));
    return (!teamId || String(task.team_id) === teamId)
      && (!status || task.status === status)
      && fromOk
      && toOk;
  });
  renderUpcoming(filtered);
}

["[data-dashboard-team]", "[data-dashboard-status]", "[data-dashboard-from]", "[data-dashboard-to]"].forEach((selector) => {
  document.querySelector(selector)?.addEventListener("change", applyDashboardFilters);
});
document.querySelector("[data-dashboard-clear]")?.addEventListener("click", () => {
  document.querySelectorAll("[data-dashboard-team], [data-dashboard-status], [data-dashboard-from], [data-dashboard-to]").forEach((control) => {
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) control.value = "";
  });
  applyDashboardFilters();
});
document.querySelector("[data-sidebar-toggle]")?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});
document.querySelector("[data-sidebar-backdrop]")?.addEventListener("click", () => {
  document.body.classList.remove("sidebar-open");
});

currentUser = await requireAuth();
if (currentUser) {
  setTexts("[data-user-name]", currentUser.full_name || "Giảng viên");
  setText("[data-user-initials]", (currentUser.full_name || "GV").split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase());
  await initializeSharedUi();
  await initializeNotifications();
  await loadDashboard();
  const hashView = window.location.hash.slice(1);
  if (hashView) document.querySelector(`[data-supervisor-view="${hashView}"]`)?.click();
}

window.addEventListener("pageshow", (event) => {
  if (event.persisted && currentUser) {
    void loadDashboard();
  }
});
