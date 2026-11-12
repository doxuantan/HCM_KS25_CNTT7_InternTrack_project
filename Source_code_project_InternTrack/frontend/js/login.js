import { ApiError } from "./api.js";
import { login, navigateByRole } from "./auth.js";

const passwordToggle = document.querySelector("[data-password-toggle]");
const passwordInput = document.querySelector("#password");

if (passwordToggle instanceof HTMLButtonElement && passwordInput instanceof HTMLInputElement) {
  passwordToggle.addEventListener("click", () => {
    const showPassword = passwordInput.type === "password";
    passwordInput.type = showPassword ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(showPassword));
    passwordToggle.setAttribute("aria-label", showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu");
  });
}

const loginForm = document.querySelector("[data-login-form]");
const loginMessage = document.querySelector("[data-login-message]");

if (loginForm instanceof HTMLFormElement && loginMessage instanceof HTMLElement) {
  const submitButton = loginForm.querySelector('button[type="submit"]');

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginMessage.hidden = false;
    loginMessage.setAttribute("role", "status");

    const formData = new FormData(loginForm);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    const remember = formData.get("remember") === "on";

    if (submitButton instanceof HTMLButtonElement) {
      submitButton.disabled = true;
    }

    loginMessage.textContent = "Đang xác thực...";

    try {
      const user = await login(email, password, remember);
      navigateByRole(user.role);
    } catch (error) {
      loginMessage.setAttribute("role", "alert");
      if (error instanceof ApiError && error.status === 401) {
        loginMessage.textContent = "Email hoặc mật khẩu không chính xác.";
      } else if (error instanceof ApiError && error.status === 403) {
        loginMessage.textContent = "Tài khoản chưa được phép truy cập. Vui lòng liên hệ quản trị viên.";
      } else if (error instanceof TypeError) {
        loginMessage.textContent = "Không thể kết nối máy chủ. Vui lòng kiểm tra kết nối và thử lại.";
      } else {
        console.error("Login failed.", error);
        loginMessage.textContent =
          error instanceof Error
            ? error.message
            : "Đăng nhập thất bại. Vui lòng thử lại.";
      }

      if (submitButton instanceof HTMLButtonElement) {
        submitButton.disabled = false;
      }
    }
  });
}