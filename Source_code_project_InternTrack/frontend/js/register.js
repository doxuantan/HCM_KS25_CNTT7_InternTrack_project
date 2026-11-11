document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
  if (!(toggle instanceof HTMLButtonElement)) {
    return;
  }

  const inputId = toggle.getAttribute("aria-controls");
  const input = inputId ? document.getElementById(inputId) : null;

  if (!(input instanceof HTMLInputElement)) {
    throw new Error("A password visibility button is missing its input.");
  }

  toggle.addEventListener("click", () => {
    const showPassword = input.type === "password";
    input.type = showPassword ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(showPassword));
    toggle.setAttribute("aria-label", showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu");
  });
});

const registerForm = document.querySelector("[data-register-form]");
const registerMessage = document.querySelector("[data-register-message]");
const passwordInput = document.querySelector("#register-password");
const confirmPasswordInput = document.querySelector("#confirm-password");

if (
  registerForm instanceof HTMLFormElement &&
  registerMessage instanceof HTMLElement &&
  passwordInput instanceof HTMLInputElement &&
  confirmPasswordInput instanceof HTMLInputElement
) {
  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    registerMessage.hidden = false;

    if (passwordInput.value !== confirmPasswordInput.value) {
      confirmPasswordInput.setAttribute("aria-invalid", "true");
      registerMessage.setAttribute("role", "alert");
      registerMessage.textContent = "Mật khẩu xác nhận chưa khớp. Vui lòng kiểm tra lại.";
      confirmPasswordInput.focus();
      return;
    }

    confirmPasswordInput.removeAttribute("aria-invalid");
    registerMessage.setAttribute("role", "status");
    registerMessage.textContent =
      "Biểu mẫu đã sẵn sàng, nhưng chức năng đăng ký chưa được kết nối với máy chủ. Thông tin của bạn chưa được gửi.";
  });

  confirmPasswordInput.addEventListener("input", () => {
    if (confirmPasswordInput.getAttribute("aria-invalid") === "true") {
      confirmPasswordInput.removeAttribute("aria-invalid");
      registerMessage.hidden = true;
    }
  });
}
