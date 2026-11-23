import { apiRequest } from "./api.js";

const TEAM_STATUS_LABELS = Object.freeze({
  ACTIVE: "Đang hoạt động",
  INACTIVE: "Tạm ngưng",
  COMPLETED: "Đã hoàn thành",
});
const PERIOD_STATUS_LABELS = Object.freeze({
  UPCOMING: "Sắp diễn ra",
  ACTIVE: "Đang diễn ra",
  COMPLETED: "Đã kết thúc",
});

function isTeam(team) {
  return (
    team !== null &&
    typeof team === "object" &&
    !Array.isArray(team) &&
    typeof team.team_name === "string" &&
    typeof team.team_code === "string" &&
    typeof team.period?.name === "string" &&
    Array.isArray(team.members)
  );
}

function createDetail(label, value) {
  const item = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value || "Chưa có dữ liệu";
  item.append(term, description);
  return item;
}

function formatDate(value) {
  if (typeof value !== "string" || !value) {
    return "—";
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(date);
}

function createMemberRow(member) {
  const row = document.createElement("tr");
  const nameCell = document.createElement("td");
  const name = document.createElement("strong");
  name.textContent = member.full_name || "Chưa có tên";
  nameCell.append(name);

  const codeCell = document.createElement("td");
  codeCell.textContent = member.student_code || "—";
  const emailCell = document.createElement("td");
  emailCell.textContent = member.email || "—";
  const roleCell = document.createElement("td");
  roleCell.textContent = member.is_leader ? "Nhóm trưởng" : "Thành viên";
  row.append(nameCell, codeCell, emailCell, roleCell);
  return row;
}

function createTeamCard(team) {
  const article = document.createElement("article");
  article.className = "panel student-team-card";

  const heading = document.createElement("div");
  heading.className = "student-team-heading";
  const titleGroup = document.createElement("div");
  const title = document.createElement("h2");
  title.textContent = team.team_name;
  const code = document.createElement("p");
  code.className = "muted";
  code.textContent = `Mã nhóm: ${team.team_code}`;
  titleGroup.append(title, code);

  const badge = document.createElement("span");
  badge.className = "student-team-badge";
  badge.textContent = TEAM_STATUS_LABELS[team.status] || "Chưa cập nhật";
  heading.append(titleGroup, badge);
  article.append(heading);

  if (team.description) {
    const description = document.createElement("p");
    description.className = "student-team-description";
    description.textContent = team.description;
    article.append(description);
  }

  const details = document.createElement("dl");
  details.className = "student-team-details";
  details.append(
    createDetail("Kỳ thực tập", team.period.name),
    createDetail(
      "Thời gian",
      `${formatDate(team.period.start_date)} – ${formatDate(team.period.end_date)}`,
    ),
    createDetail(
      "Trạng thái kỳ",
      PERIOD_STATUS_LABELS[team.period.status] || "Chưa cập nhật",
    ),
    createDetail(
      "Giảng viên hướng dẫn",
      team.supervisor?.full_name,
    ),
  );
  article.append(details);

  const membersHeading = document.createElement("h3");
  membersHeading.className = "student-team-members-heading";
  membersHeading.textContent = `Thành viên (${team.members.length})`;
  article.append(membersHeading);

  const tableWrapper = document.createElement("div");
  tableWrapper.className = "table-scroll";
  const table = document.createElement("table");
  table.className = "data-table student-team-table";
  const header = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of ["Họ tên", "Mã sinh viên", "Email", "Vai trò"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    headerRow.append(cell);
  }
  header.append(headerRow);
  const body = document.createElement("tbody");
  body.append(...team.members.map(createMemberRow));
  table.append(header, body);
  tableWrapper.append(table);
  article.append(tableWrapper);
  return article;
}

function renderTeamState(state, message) {
  const list = document.querySelector("[data-team-list]");
  if (!(list instanceof HTMLElement)) {
    return;
  }
  const status = document.createElement("p");
  status.className = "student-team-state";
  status.dataset.teamState = "";
  status.dataset.state = state;
  status.setAttribute("role", state === "error" ? "alert" : "status");
  status.textContent = message;
  list.replaceChildren(status);
  list.setAttribute("aria-busy", String(state === "loading"));
}

export async function initializeStudentTeam(user) {
  const studentName = document.querySelector("[data-student-name]");
  const mainContent = document.querySelector("#main-content");
  if (studentName) {
    studentName.textContent =
      typeof user.full_name === "string" && user.full_name.trim()
        ? user.full_name.trim()
        : "sinh viên";
  }

  try {
    const teams = await apiRequest("teams/me");
    if (!Array.isArray(teams) || !teams.every(isTeam)) {
      throw new TypeError("API nhóm trả về dữ liệu không hợp lệ.");
    }
    if (teams.length === 0) {
      renderTeamState("empty", "Bạn chưa được phân vào nhóm thực tập nào.");
    } else {
      const list = document.querySelector("[data-team-list]");
      if (list instanceof HTMLElement) {
        list.replaceChildren(...teams.map(createTeamCard));
        list.setAttribute("aria-busy", "false");
      }
    }
  } catch (error) {
    console.error("Student team data could not be loaded.", error);
    renderTeamState(
      "error",
      "Không thể tải thông tin nhóm. Vui lòng tải lại trang hoặc kiểm tra kết nối.",
    );
  } finally {
    if (mainContent instanceof HTMLElement) {
      mainContent.setAttribute("aria-busy", "false");
    }
  }
}
