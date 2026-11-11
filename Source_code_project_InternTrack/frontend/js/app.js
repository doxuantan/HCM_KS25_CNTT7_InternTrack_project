import { loadComponents } from "./component-loader.js";

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

try {
  await loadComponents();
  setupSidebar();
} catch (error) {
  console.error("The application layout could not be initialized.", error);
  const main = document.querySelector("#main-content");
  if (main) {
    const message = document.createElement("p");
    message.className = "load-error";
    message.setAttribute("role", "alert");
    message.textContent = "Không thể tải đầy đủ giao diện. Vui lòng tải lại trang hoặc kiểm tra kết nối.";
    main.prepend(message);
  }
}
