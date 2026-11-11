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

const JWT_SHAPE = /^[A-Za-z0-9_-]{1,2000}\.[A-Za-z0-9_-]{1,4000}\.[A-Za-z0-9_-]{1,2000}$/;

/** The value if it is a JWT (three base64url parts), otherwise null. */
function jwtOrNull(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const match = JWT_SHAPE.exec(value);
  return match ? match[0] : null;
}

// A renewed access token lives only in memory (never written to browser storage). After a page
// reload the stored, expired token is renewed again with the stored refresh token.
let renewedToken: string | null = null;
let refreshing: Promise<boolean> | null = null;

/** The access token to send: the renewed one if there is one, else the one stored at sign-in. */
export function currentToken(): string | null {
  return renewedToken ?? localStorage.getItem(TOKEN_KEY);
}

/**
 * Gets a new access token with the refresh token (the access token only lives for an hour; the
 * refresh token from sign-in lasts a week).
 * Several requests failing at once share one refresh. False when there is nothing to refresh
 * with or the server refuses it, i.e. the person really has to sign in again.
 */
function refreshAccessToken(): Promise<boolean> {
  refreshing ??= (async () => {
    const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refresh) return false;
    try {
      const res = await fetch(`${BASE}/api/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return false;
      const data = (await res.json()) as { access?: unknown };
      // Only ever use something shaped like a token, whatever the response contains
      const access = jwtOrNull(data.access);
      if (!access) return false;
      renewedToken = access;
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

function send(path: string, init: RequestInit): Promise<Response> {
  const token = currentToken();
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(`${BASE}${path}`, { ...init, headers });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const hadToken = Boolean(currentToken());
  let res = await send(path, init);
  // An expired access token: get a new one with the refresh token and try once more
  if (res.status === 401 && hadToken && (await refreshAccessToken())) {
    res = await send(path, init);
  }
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

/** True when the server says the session is no longer valid (as opposed to a network hiccup). */
export function isSignedOutError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

/** Downloads an authenticated file (e.g. an invoice PDF) and hands it to the browser as a download. */
export async function downloadFile(path: string, filename: string) {
  const authorized = () => {
    const token = currentToken();
    return fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  };
  let res = await authorized();
  if (res.status === 401 && (await refreshAccessToken())) res = await authorized();
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, (data as { error?: string }).error || "Download failed");
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function saveSession(token: string, user: User, refreshToken?: string) {
  renewedToken = null; // a new sign-in replaces any token renewed for the previous one
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
  renewedToken = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function readUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}
