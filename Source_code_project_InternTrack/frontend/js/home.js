import { ApiError, getAccessToken } from "./api.js";
import { getCurrentUser, logout, navigateByRole } from "./auth.js";

const roleNotice = document.querySelector("[data-role-notice]");
const logoutButton = document.querySelector("[data-home-logout]");

if (!(roleNotice instanceof HTMLElement) || !(logoutButton instanceof HTMLButtonElement)) {
  throw new Error("The home page is missing its session controls.");
}

logoutButton.addEventListener("click", logout);

async function initializeHomeSession() {
  try {
    if (!getAccessToken()) {
      return;
    }

    const user = await getCurrentUser();
    if (user.role === "STUDENT") {
      navigateByRole(user.role);
      return;
    }

    if (user.role !== "ADMIN" && user.role !== "SUPERVISOR") {
      throw new Error("Role của tài khoản không được hỗ trợ.");
    }

    const roleLabel = user.role === "ADMIN" ? "ADMIN" : "SUPERVISOR";
    roleNotice.textContent =
      `Bạn đã đăng nhập với vai trò ${roleLabel}. Giao diện dành cho vai trò này chưa hoàn thiện; ` +
      "phiên đăng nhập đã được lưu và không hiển thị dữ liệu của sinh viên.";
    roleNotice.hidden = false;
    document.querySelectorAll("[data-public-login], [data-public-register]").forEach((link) => {
      link.setAttribute("hidden", "");
    });
    logoutButton.hidden = false;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return;
    }

    roleNotice.textContent =
      error instanceof ApiError && error.status === 0
        ? `Không thể kiểm tra phiên đăng nhập. ${error.message}`
        : "Không thể kiểm tra phiên đăng nhập. Vui lòng thử tải lại trang.";
    roleNotice.setAttribute("role", "alert");
    roleNotice.hidden = false;
  }
}

void initializeHomeSession();
