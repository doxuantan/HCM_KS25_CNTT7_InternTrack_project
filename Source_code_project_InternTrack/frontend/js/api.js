const TOKEN_KEY = "intertrack.access_token";

const configuredApiUrl =
  document.querySelector('meta[name="api-base-url"]')?.getAttribute("content")?.trim() ||
  window.INTERTRACK_API_BASE_URL ||
  "http://localhost:8000/api/v1";
const API_BASE_URL = configuredApiUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

export function setAuthSession(accessToken, remember = false) {
  clearAuthSession();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(TOKEN_KEY, accessToken);
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

function redirectToLogin() {
  if (!window.location.pathname.endsWith("/login.html")) {
    window.location.replace(new URL("./login.html", window.location.href));
  }
}

async function readResponse(response) {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    return text ? { detail: text } : null;
  }

  try {
    return await response.json();
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new ApiError("API trả về dữ liệu không hợp lệ.", response.status);
    }
    throw error;
  }
}

export async function apiRequest(path, options = {}) {
  const { body, headers: requestHeaders, ...requestOptions } = options;
  const headers = new Headers(requestHeaders);
  const token = getAccessToken();

  if (token) {
    headers.set("Authorization", "Bearer " + token);
  }
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(
    new URL(`${API_BASE_URL}/${path.replace(/^\/+/, "")}`, window.location.href),
    {
      ...requestOptions,
      headers,
      body:
        body === undefined || body instanceof FormData
          ? body
          : JSON.stringify(body),
    },
  );
  const payload = await readResponse(response);

  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Yêu cầu thất bại (${response.status}).`;

    if (response.status === 401 && token) {
      clearAuthSession();
      redirectToLogin();
    }

    throw new ApiError(message, response.status, payload);
  }

  return payload;
}