import { TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY, type User } from "../types";

const BASE = "";

export class ApiError extends Error {
  status: number;
  data?: Record<string, unknown>;
  constructor(status: number, message: string, data?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const errorMsg =
      (data as { error?: string; detail?: string; message?: string }).error ||
      (data as { detail?: string }).detail ||
      (data as { message?: string }).message ||
      "Request failed";
    throw new ApiError(res.status, errorMsg, data as Record<string, unknown>);
  }

  return data as T;
}

export function saveSession(token: string, user: User, refreshToken?: string) {
  localStorage.setItem(TOKEN_KEY, token);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
  // Standardize role to lowercase for frontend routes
  const normalizedUser: User = {
    ...user,
    role: (user.role.toLowerCase() as User["role"]),
    name: user.name || user.email?.split("@")[0] || user.phone || "User",
  };
  localStorage.setItem(USER_KEY, JSON.stringify(normalizedUser));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function readUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}
