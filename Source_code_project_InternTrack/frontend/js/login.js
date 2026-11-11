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
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loginMessage.textContent =
      "Giao diện đã sẵn sàng, nhưng chức năng xác thực chưa được kết nối. Thông tin đăng nhập chưa được gửi.";
    loginMessage.hidden = false;
  });
}