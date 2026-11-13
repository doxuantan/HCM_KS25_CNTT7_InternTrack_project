import { ApiError, getAccessToken } from "./api.js";
import { getCurrentUser, login, navigateByRole } from "./auth.js";

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
const emailInput = document.querySelector("#email");
const submitButton = loginForm?.querySelector('button[type="submit"]');

if (
  !(loginForm instanceof HTMLFormElement) ||
  !(loginMessage instanceof HTMLElement) ||
  !(emailInput instanceof HTMLInputElement) ||
  !(passwordInput instanceof HTMLInputElement) ||
  !(submitButton instanceof HTMLButtonElement)
) {
  throw new Error("The login form is missing a required element.");
}

loginForm.noValidate = true;

function createFieldError(input) {
  const error = document.createElement("span");
  error.className = "login-field-error";
  error.id = `${input.id}-error`;
  error.hidden = true;
  input.closest(".form-field").append(error);
  input.setAttribute("aria-describedby", error.id);
  return error;
}

const emailError = createFieldError(emailInput);
const passwordError = createFieldError(passwordInput);
const submitLabel = Array.from(submitButton.childNodes).find(
  (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
);
const originalSubmitLabel = submitLabel?.nodeValue;
let hasAttemptedSubmit = false;
let isSubmitting = false;

function getEmailError() {
  if (!emailInput.value.trim()) {
    return "Vui lòng nhập email.";
  }
  if (emailInput.validity.typeMismatch) {
    return "Vui lòng nhập địa chỉ email hợp lệ.";
  }
  return "";
}

function getPasswordError() {
  return passwordInput.value.length === 0 ? "Vui lòng nhập mật khẩu." : "";
}

function updateFieldError(input, errorElement, message) {
  errorElement.textContent = message;
  errorElement.hidden = !message;
  if (message) {
    input.setAttribute("aria-invalid", "true");
  } else {
    input.removeAttribute("aria-invalid");
  }
}

function clearLoginMessage() {
  loginMessage.hidden = true;
  loginMessage.textContent = "";
  loginMessage.setAttribute("role", "status");
}

function showLoginError(error) {
  loginMessage.setAttribute("role", "alert");
  if (error instanceof ApiError && error.status === 401) {
    loginMessage.textContent = "Email hoặc mật khẩu không chính xác.";
  } else if (error instanceof ApiError && error.status === 403) {
    loginMessage.textContent =
      "Tài khoản chưa được phép truy cập. Vui lòng liên hệ quản trị viên.";
  } else if (error instanceof ApiError && error.status === 429) {
    loginMessage.textContent = "Quá nhiều lần đăng nhập. Vui lòng chờ và thử lại.";
  } else if (error instanceof ApiError && error.status >= 500) {
    loginMessage.textContent = "Máy chủ đang gặp sự cố. Vui lòng thử lại sau.";
  } else if (error instanceof ApiError && error.status === 0) {
    loginMessage.textContent = error.message;
  } else if (error instanceof TypeError) {
    loginMessage.textContent =
      "Không thể kết nối máy chủ. Vui lòng kiểm tra API, kết nối mạng và cấu hình CORS.";
  } else {
    loginMessage.textContent = "Đăng nhập thất bại. Vui lòng kiểm tra thông tin và thử lại.";
  }
  loginMessage.hidden = false;
}

function validateFields() {
  const emailMessage = getEmailError();
  const passwordMessage = getPasswordError();
  updateFieldError(emailInput, emailError, emailMessage);
  updateFieldError(passwordInput, passwordError, passwordMessage);
  return !emailMessage && !passwordMessage;
}

for (const input of [emailInput, passwordInput]) {
  input.addEventListener("input", () => {
    clearLoginMessage();
    if (hasAttemptedSubmit) {
      validateFields();
    }
  });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isSubmitting) {
    return;
  }

  hasAttemptedSubmit = true;
  clearLoginMessage();
  if (!validateFields()) {
    (getEmailError() ? emailInput : passwordInput).focus();
    return;
  }

  isSubmitting = true;
  submitButton.disabled = true;
  submitButton.setAttribute("aria-busy", "true");
  if (submitLabel) {
    submitLabel.nodeValue = " Đang đăng nhập... ";
  }
  loginMessage.textContent = "Đang xác thực...";
  loginMessage.hidden = false;
  loginMessage.setAttribute("role", "status");

  try {
    const remember = new FormData(loginForm).get("remember") === "on";
    const user = await login(emailInput.value.trim(), passwordInput.value, remember);
    navigateByRole(user.role);
  } catch (error) {
    showLoginError(error);
  } finally {
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.removeAttribute("aria-busy");
    if (submitLabel && originalSubmitLabel !== undefined) {
      submitLabel.nodeValue = originalSubmitLabel;
    }
  }
});

async function redirectAuthenticatedUser() {
  try {
    if (!getAccessToken()) {
      return;
    }

    isSubmitting = true;
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
    loginMessage.textContent = "Đang kiểm tra phiên đăng nhập...";
    loginMessage.hidden = false;
    loginMessage.setAttribute("role", "status");

    const user = await getCurrentUser();
    navigateByRole(user.role);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearLoginMessage();
      return;
    }
    showLoginError(error);
  } finally {
    isSubmitting = false;
    submitButton.disabled = false;
    submitButton.removeAttribute("aria-busy");
  }
}

void redirectAuthenticatedUser();
