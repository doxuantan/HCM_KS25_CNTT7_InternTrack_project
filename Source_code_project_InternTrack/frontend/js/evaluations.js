import { apiRequest } from "./api.js";
import { requireAuth } from "./auth.js";
import { initializeNotifications } from "./notifications.js";
import { initializeSharedUi } from "./ui.js";

function render(evaluations) {
  const container = document.querySelector("[data-evaluation-results]");
  if (!(container instanceof HTMLElement)) return;
  if (!evaluations.length) {
    container.textContent = "Chưa có kết quả đánh giá được công bố.";
    return;
  }
  container.replaceChildren(...evaluations.map((evaluation) => {
    const article = document.createElement("article");
    article.className = "panel student-tasks-panel";
    const heading = document.createElement("div");
    heading.className = "panel-heading student-panel-heading";
    const title = document.createElement("h2");
    title.textContent = `Đánh giá kỳ #${evaluation.period_id}`;
    const score = document.createElement("strong");
    score.textContent = evaluation.total_score == null ? "Chưa nhập điểm" : `Tổng điểm: ${evaluation.total_score}`;
    heading.append(title, score);
    article.append(heading);

    if (evaluation.comment) {
      const comment = document.createElement("p");
      comment.textContent = evaluation.comment;
      article.append(comment);
    }

    if (evaluation.details?.length) {
      const table = document.createElement("table");
      table.className = "data-table student-task-table";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      for (const label of ["Tiêu chí", "Trọng số", "Điểm", "Nhận xét"]) {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = label;
        headRow.append(cell);
      }
      head.append(headRow);
      table.append(head);
      const body = document.createElement("tbody");
      for (const detail of evaluation.details) {
        const row = document.createElement("tr");
        for (const value of [
          detail.criteria_name || `Tiêu chí #${detail.criteria_id}`,
          detail.weight ?? "—",
          detail.score,
          detail.comment || "—",
        ]) {
          const cell = document.createElement("td");
          cell.textContent = String(value);
          row.append(cell);
        }
        body.append(row);
      }
      table.append(body);
      article.append(table);
    }
    return article;
  }));
}

async function loadEvaluations() {
  const container = document.querySelector("[data-evaluation-results]");
  if (!(container instanceof HTMLElement)) return;
  container.textContent = "Đang tải kết quả đánh giá...";
  try {
    const evaluations = await apiRequest("evaluations");
    if (!Array.isArray(evaluations)) throw new Error("API đánh giá trả về dữ liệu không hợp lệ.");
    render(evaluations);
  } catch (error) {
    container.textContent = `Không thể tải kết quả đánh giá: ${error.message}`;
    container.setAttribute("role", "alert");
  }
}

try {
  const user = await requireAuth();
  if (user) {
    await initializeSharedUi();
    await initializeNotifications();
    await loadEvaluations();
    document.querySelector("#main-content")?.setAttribute("aria-busy", "false");
  }
} catch (error) {
  const container = document.querySelector("[data-evaluation-results]");
  if (container) {
    container.textContent = `Không thể khởi tạo trang đánh giá: ${error.message}`;
    container.setAttribute("role", "alert");
  }
}