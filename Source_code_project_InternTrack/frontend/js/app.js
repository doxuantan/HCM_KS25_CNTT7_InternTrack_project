import { loadComponents } from "./component-loader.js";
import { logout, requireAuth } from "./auth.js";
import { initializeStudentDashboard } from "./student-dashboard.js";

function getUserInitials(fullName) {
  const nameParts = fullName.trim().split(/\s+/).filter(Boolean);
  return nameParts
    .slice(-2)
    .map((part) => Array.from(part)[0].toLocaleUpperCase("vi-VN"))
    .join("") || "SV";
}

function setupSidebar() {
  const toggle = document.querySelector("[data-sidebar-toggle]");
  const backdrop = document.querySelector("[data-sidebar-backdrop]");

  if (!(toggle instanceof HTMLButtonElement) || !(backdrop instanceof HTMLElement)) {
    throw new Error("Sidebar controls are missing from the page.");
  }

  const setSidebarOpen = (isOpen) => {
    document.body.classList.toggle("sidebar-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Đóng menu điều hướng" : "Mở menu điều hướng");
  };

  toggle.addEventListener("click", () => {
    setSidebarOpen(!document.body.classList.contains("sidebar-open"));
  });
  backdrop.addEventListener("click", () => setSidebarOpen(false));
  document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
    link.addEventListener("click", () => setSidebarOpen(false));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setSidebarOpen(false);
    }
  });
}

function setupAccountMenu(user) {
  const container = document.querySelector("[data-account-menu]");
  const toggle = container?.querySelector("[data-account-toggle]");
  const menu = container?.querySelector("#account-menu");
  const logoutLink = container?.querySelector("[data-logout-link]");

  if (
    !(container instanceof HTMLElement) ||
    !(toggle instanceof HTMLButtonElement) ||
    !(menu instanceof HTMLElement) ||
    !(logoutLink instanceof HTMLAnchorElement)
  ) {
    throw new Error("Account menu controls are missing from the page.");
  }

  const roleLabels = {
    ADMIN: "Quản trị viên",
    SUPERVISOR: "Giảng viên hướng dẫn",
    STUDENT: "Sinh viên",
  };
  const roleLabel = roleLabels[user.role] || user.role;
  container.querySelectorAll("[data-user-name]").forEach((element) => {
    element.textContent = user.full_name;
  });
  container.querySelectorAll("[data-user-role]").forEach((element) => {
    element.textContent = roleLabel;
  });
  const initials = container.querySelector("[data-user-initials]");
  if (initials) {
    initials.textContent = getUserInitials(user.full_name);
  }
  toggle.setAttribute("aria-label", `Tài khoản ${user.full_name}`);
  logoutLink.addEventListener("click", (event) => {
    event.preventDefault();
    logout();
  });

  const setMenuOpen = (isOpen) => {
    menu.hidden = !isOpen;
    toggle.setAttribute("aria-expanded", String(isOpen));
  };

  toggle.addEventListener("click", () => {
    setMenuOpen(menu.hidden);
  });

  document.addEventListener("click", (event) => {
    if (event.target instanceof Node && !container.contains(event.target)) {
      setMenuOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !menu.hidden) {
      setMenuOpen(false);
      toggle.focus();
    }
  });
}

try {
  const user = await requireAuth();
  if (user) {
    await loadComponents();
    setupSidebar();
    setupAccountMenu(user);
    if (document.body.dataset.dashboard === "student") {
      initializeStudentDashboard(user);
    }
  }
} catch (error) {
  console.error("The application layout could not be initialized.", error);
  const main = document.querySelector("#main-content");
  if (main) {
    main.setAttribute("aria-busy", "false");
    const message = document.createElement("p");
    message.className = "load-error";
    message.setAttribute("role", "alert");
    message.textContent = "Không thể tải đầy đủ giao diện. Vui lòng tải lại trang hoặc kiểm tra kết nối.";
    main.prepend(message);
  }
}
