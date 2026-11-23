import { apiRequest, downloadAttachment } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeNotifications } from "./notifications.js";
import { initializeSharedUi, showToast } from "./ui.js";

let diaries = [];
let editingDiaryId = null;

function state(message, isError = false) {
  const body = document.querySelector("[data-diary-rows]");
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

function cell(value) {
  const element = document.createElement("td");
  element.textContent = value == null || value === "" ? "—" : String(value);
  return element;
}

function statusName(value) {
  return ({
    DRAFT: "Bản nháp",
    SUBMITTED: "Đã nộp",
    REVIEWED: "Đã nhận xét",
    REVISION_REQUIRED: "Yêu cầu sửa",
  })[value] || value;
}

function renderDiaries() {
  const body = document.querySelector("[data-diary-rows]");
  if (!(body instanceof HTMLTableSectionElement)) return;
  if (!diaries.length) {
    state("Bạn chưa có nhật ký thực tập.");
    return;
  }

  body.replaceChildren(...diaries.map((diary) => {
    const row = document.createElement("tr");
    const content = document.createElement("td");
    content.textContent = diary.work_content;
    if (diary.result) {
      const result = document.createElement("p");
      result.className = "muted";
      result.textContent = `Kết quả: ${diary.result}`;
      content.append(result);
    }

    const reviewCell = document.createElement("td");
    reviewCell.textContent = statusName(diary.status);
    for (const review of diary.reviews || []) {
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = `${statusName(review.status)}: ${review.content}`;
      reviewCell.append(note);
    }

    const actions = document.createElement("td");
    const attachmentButton = document.createElement("button");
    attachmentButton.type = "button";
    attachmentButton.className = "admin-row-action";
    attachmentButton.dataset.diaryAttachments = String(diary.id);
    attachmentButton.textContent = "Minh chứng";
    actions.append(attachmentButton);
    if (diary.status === "DRAFT") {
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "admin-row-action";
      editButton.dataset.editDiary = String(diary.id);
      editButton.textContent = "Chỉnh sửa";
      actions.append(editButton);
    }

    row.append(
      cell(diary.work_date),
      content,
      cell(diary.difficulties),
      reviewCell,
      actions,
    );
    return row;
  }));
}

async function loadDiaries() {
  state("Đang tải nhật ký...");
  try {
    const params = new URLSearchParams();
    const workDate = document.querySelector("[data-diary-date]")?.value;
    const diaryStatus = document.querySelector("[data-diary-status]")?.value;
    if (workDate) params.set("work_date", workDate);
    if (diaryStatus) params.set("status", diaryStatus);
    const query = params.size ? `?${params}` : "";
    diaries = await apiRequest(`diaries${query}`);
    if (!Array.isArray(diaries)) {
      throw new Error("API nhật ký trả về dữ liệu không hợp lệ.");
    }
    renderDiaries();
  } catch (error) {
    diaries = [];
    state(`Không thể tải nhật ký: ${error.message}`, true);
  }
}

function populateForm(diary) {
  const form = document.querySelector("[data-diary-form]");
  if (!(form instanceof HTMLFormElement)) return;
  editingDiaryId = diary?.id ?? null;
  form.elements.work_date.value = diary?.work_date || new Date().toISOString().slice(0, 10);
  form.elements.work_content.value = diary?.work_content || "";
  form.elements.result.value = diary?.result || "";
  form.elements.difficulties.value = diary?.difficulties || "";
  form.elements.lessons_learned.value = diary?.lessons_learned || "";
  form.elements.task_id.value = diary?.task_id || "";
  const title = document.querySelector("[data-diary-form-title]");
  if (title) title.textContent = editingDiaryId ? "Chỉnh sửa nhật ký được yêu cầu bổ sung" : "Tạo nhật ký thực tập";
}

async function saveDiary(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!(form instanceof HTMLFormElement)) return;
  const file = form.elements.evidence.files[0];
  const taskId = Number(form.elements.task_id.value);
  const payload = {
    work_date: form.elements.work_date.value,
    work_content: form.elements.work_content.value.trim(),
    result: form.elements.result.value.trim() || null,
    difficulties: form.elements.difficulties.value.trim() || null,
    lessons_learned: form.elements.lessons_learned.value.trim() || null,
    task_id: taskId || null,
  };
  const wasEditing = editingDiaryId !== null;
  try {
    const diary = wasEditing
      ? await apiRequest(`diaries/${editingDiaryId}`, { method: "PUT", body: payload })
      : await apiRequest("diaries", { method: "POST", body: payload });
    if (file) {
      const body = new FormData();
      body.set("diary_id", String(diary.id));
      body.set("file", file);
      await apiRequest("attachments/upload", { method: "POST", body });
    }
    form.reset();
    populateForm(null);
    showToast(wasEditing ? "Đã cập nhật và nộp lại nhật ký." : "Đã tạo nhật ký.");
    await loadDiaries();
  } catch (error) {
    showToast(error.message, { kind: "error" });
  }
}

document.querySelector("[data-diary-form]")?.addEventListener("submit", (event) => void saveDiary(event));
document.querySelector("[data-diary-status]")?.addEventListener("change", () => void loadDiaries());
document.querySelector("[data-diary-date]")?.addEventListener("change", () => void loadDiaries());
document.querySelector("[data-diary-clear-filters]")?.addEventListener("click", () => {
  document.querySelector("[data-diary-status]").value = "";
  document.querySelector("[data-diary-date]").value = "";
  void loadDiaries();
});
document.querySelector("[data-diary-rows]")?.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const edit = target?.closest("[data-edit-diary]");
  if (edit) {
    const diary = diaries.find((item) => item.id === Number(edit.dataset.editDiary));
    if (diary) {
      populateForm(diary);
      document.querySelector("[data-diary-form-title]")?.scrollIntoView({ behavior: "smooth" });
    }
    return;
  }
  const attachments = target?.closest("[data-diary-attachments]");
  if (!attachments) return;
  const row = attachments.closest("tr");
  const oldList = row?.querySelector("[data-attachment-list]");
  if (oldList) {
    oldList.remove();
    return;
  }
  const list = document.createElement("div");
  list.dataset.attachmentList = "";
  list.textContent = "Đang tải minh chứng...";
  attachments.closest("td")?.append(list);
  void apiRequest(`attachments?diary_id=${encodeURIComponent(attachments.dataset.diaryAttachments)}`)
    .then((items) => {
      list.replaceChildren();
      if (!items.length) {
        list.textContent = "Chưa có minh chứng.";
        return;
      }
      for (const item of items) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "admin-row-action";
        button.textContent = item.file_name;
        button.addEventListener("click", () => {
          void downloadAttachment(item.id, item.file_name)
            .catch((error) => showToast(error.message, { kind: "error" }));
        });
        list.append(button);
      }
    })
    .catch((error) => {
      list.textContent = `Không tải được minh chứng: ${error.message}`;
    });
});

try {
  const user = await requireAuth();
  if (user) {
    await initializeSharedUi();
    await initializeNotifications();
    populateForm(null);
    await loadDiaries();
  }
} catch (error) {
  state(`Không thể khởi tạo trang nhật ký: ${error.message}`, true);
}