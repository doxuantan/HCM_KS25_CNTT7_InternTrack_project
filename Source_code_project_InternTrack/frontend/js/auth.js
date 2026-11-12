import { apiRequest, clearAuthSession, getAccessToken, setAuthSession } from "./api.js";

const ROLE_HOME = Object.freeze({
  ADMIN: "index.html",
  SUPERVISOR: "index.html",
  STUDENT: "index.html",
});

export async function login(email, password, remember = false) {
  const result = await apiRequest("auth/login", {
    method: "POST",
    body: { email, password },
  });

  if (
    typeof result?.access_token !== "string" ||
    !result.access_token ||
    !result.user ||
    !Object.hasOwn(ROLE_HOME, result.user.role)
  ) {
    throw new Error("API đăng nhập trả về dữ liệu không hợp lệ.");
  }

  setAuthSession(result.access_token, remember);
  return result.user;
}

export async function getCurrentUser() {
  return apiRequest("auth/me");
}

export function navigateByRole(role) {
  const destination = ROLE_HOME[role];
  if (!destination) {
    throw new Error(`Role không được hỗ trợ: ${role}`);
  }
  window.location.assign(new URL(destination, window.location.href));
}

export async function requireAuth() {
  if (!getAccessToken()) {
    window.location.replace(new URL("./login.html", window.location.href));
    return null;
  }

  const user = await getCurrentUser();
  const allowedRoles = document.body.dataset.allowedRoles
    ?.split(",")
    .map((role) => role.trim())
    .filter(Boolean);

  if (allowedRoles?.length && !allowedRoles.includes(user.role)) {
    navigateByRole(user.role);
    return null;
  }

  return user;
}

export function logout() {
  clearAuthSession();
  window.location.replace(new URL("./login.html", window.location.href));
}