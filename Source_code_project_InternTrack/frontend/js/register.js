import { ApiError } from "./api.js";
import { register } from "./auth.js";

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
const fullNameInput = document.querySelector("#full-name");
const emailInput = document.querySelector("#register-email");
const passwordInput = document.querySelector("#register-password");
const confirmPasswordInput = document.querySelector("#confirm-password");
const submitButton = registerForm?.querySelector('button[type="submit"]');

if (
  registerForm instanceof HTMLFormElement &&
  registerMessage instanceof HTMLElement &&
  fullNameInput instanceof HTMLInputElement &&
  emailInput instanceof HTMLInputElement &&
  passwordInput instanceof HTMLInputElement &&
  confirmPasswordInput instanceof HTMLInputElement &&
  submitButton instanceof HTMLButtonElement
) {
  let isSubmitting = false;
  let redirectingToLogin = false;
  const submitLabel = Array.from(submitButton.childNodes).find(
    (node) => node.nodeType === Node.TEXT_NODE,
  );
  const originalSubmitLabel = submitLabel?.textContent.trim() || "Tạo tài khoản";

  function showMessage(message, role = "alert") {
    registerMessage.hidden = false;
    registerMessage.setAttribute("role", role);
    registerMessage.textContent = message;
  }

  function clearMessage() {
    registerMessage.hidden = true;
    registerMessage.textContent = "";
    registerMessage.setAttribute("role", "status");
  }

  function setSubmitting(submitting) {
    submitButton.disabled = submitting;
    submitButton.setAttribute("aria-busy", String(submitting));
    if (submitLabel) {
      submitLabel.textContent = submitting
        ? "Đang tạo tài khoản... "
        : `${originalSubmitLabel} `;
    }
  }

  function getErrorMessage(error) {
    if (error instanceof ApiError) {
      if (error.status === 409) {
        return "Email này đã được đăng ký. Vui lòng sử dụng email khác hoặc đăng nhập.";
      }
      if (error.status === 422) {
        return "Thông tin đăng ký chưa hợp lệ. Vui lòng kiểm tra lại các trường.";
      }
      if (error.status >= 500) {
        return "Máy chủ đang gặp sự cố. Vui lòng thử lại sau.";
      }
    } else if (error instanceof TypeError) {
      return "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối và thử lại.";
    }

    return "Đăng ký chưa thành công. Vui lòng thử lại.";
  }

  function clearResolvedFieldErrors() {
    if (
      fullNameInput.getAttribute("aria-invalid") === "true" &&
      fullNameInput.value.trim()
    ) {
      fullNameInput.removeAttribute("aria-invalid");
      clearMessage();
    }

    if (
      confirmPasswordInput.getAttribute("aria-invalid") === "true" &&
      confirmPasswordInput.value === passwordInput.value
    ) {
      confirmPasswordInput.removeAttribute("aria-invalid");
      clearMessage();
    }
  }

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    if (!registerForm.reportValidity()) {
      return;
    }

    const fullName = fullNameInput.value.trim();
    if (!fullName) {
      fullNameInput.setAttribute("aria-invalid", "true");
      showMessage("Vui lòng nhập họ và tên.");
      fullNameInput.focus();
      return;
    }

    if (passwordInput.value !== confirmPasswordInput.value) {
      confirmPasswordInput.setAttribute("aria-invalid", "true");
      showMessage("Mật khẩu xác nhận chưa khớp. Vui lòng kiểm tra lại.");
      confirmPasswordInput.focus();
      return;
    }

    fullNameInput.removeAttribute("aria-invalid");
    confirmPasswordInput.removeAttribute("aria-invalid");
    isSubmitting = true;
    setSubmitting(true);
    showMessage("Đang tạo tài khoản...", "status");

    try {
      await register(emailInput.value.trim(), passwordInput.value, fullName);
      redirectingToLogin = true;
      showMessage("Đăng ký thành công. Đang chuyển đến trang đăng nhập...", "status");
      passwordInput.value = "";
      confirmPasswordInput.value = "";
      window.setTimeout(() => {
        window.location.assign(new URL("./login.html", window.location.href));
      }, 900);
    } catch (error) {
      showMessage(getErrorMessage(error));
    } finally {
      if (!redirectingToLogin) {
        isSubmitting = false;
        setSubmitting(false);
      }
    }
  });

  fullNameInput.addEventListener("input", clearResolvedFieldErrors);
  passwordInput.addEventListener("input", clearResolvedFieldErrors);
  confirmPasswordInput.addEventListener("input", clearResolvedFieldErrors);
}
