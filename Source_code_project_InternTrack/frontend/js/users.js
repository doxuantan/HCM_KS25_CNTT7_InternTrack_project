import { apiRequest } from "./api.js";

const USER_PAGE_SIZE = 100;

function getUserPath(userId) {
  const numericId = Number(userId);
  if (!Number.isSafeInteger(numericId) || numericId < 1) {
    throw new TypeError("Mã người dùng không hợp lệ.");
  }
  return `users/${numericId}`;
}

export async function listUsers() {
  const users = [];
  let skip = 0;

  while (true) {
    const page = await apiRequest(`users?skip=${skip}&limit=${USER_PAGE_SIZE}`);
    if (
      !Array.isArray(page) ||
      page.some((user) => user === null || typeof user !== "object" || Array.isArray(user))
    ) {
      throw new Error("API người dùng trả về dữ liệu không hợp lệ.");
    }

    users.push(...page);
    if (page.length < USER_PAGE_SIZE) {
      return users;
    }
    skip += page.length;
  }
}

export function createUser(user) {
  return apiRequest("users", {
    method: "POST",
    body: user,
  });
}

export function updateUser(userId, user) {
  return apiRequest(getUserPath(userId), {
    method: "PUT",
    body: user,
  });
}

export function setUserActive(userId, isActive) {
  if (typeof isActive !== "boolean") {
    throw new TypeError("Trạng thái người dùng không hợp lệ.");
  }
  return apiRequest(`${getUserPath(userId)}/status`, {
    method: "PATCH",
    body: { is_active: isActive },
  });
}