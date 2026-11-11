import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, isSignedOutError } from "./api";

const store = new Map<string, string>();
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

// Token-shaped values (three base64url parts), as the server issues them
const NEW = "aGVhZGVy.bmV3LWFjY2Vzcw.c2ln";
const R2 = "aGVhZGVy.bmV3LXJlZnJlc2g.c2ln";

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
});
afterEach(() => vi.unstubAllGlobals());

function authHeader(call: unknown[]) {
  return new Headers((call[1] as RequestInit).headers).get("Authorization");
}

describe("api", () => {
  it("renews an expired access token with the refresh token and repeats the request", async () => {
    store.set("doorstep_token", "old");
    store.set("doorstep_refresh_token", "r1");
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/auth/refresh/") return json(200, { access: NEW, refresh: R2 });
      return new Headers(init?.headers).get("Authorization") === `Bearer ${NEW}` ? json(200, { ok: true }) : json(401, { detail: "Token expired" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api("/api/bookings/")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["/api/bookings/", "/api/auth/refresh/", "/api/bookings/"]);
    expect(authHeader(fetchMock.mock.calls[2])).toBe(`Bearer ${NEW}`);
    expect(store.get("doorstep_token")).toBe(NEW);
    expect(store.get("doorstep_refresh_token")).toBe(R2);
  });

  it("refreshes once when several requests fail together", async () => {
    store.set("doorstep_token", "old");
    store.set("doorstep_refresh_token", "r1");
    let refreshes = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/auth/refresh/") {
        refreshes += 1;
        return json(200, { access: NEW });
      }
      return new Headers(init?.headers).get("Authorization") === `Bearer ${NEW}` ? json(200, {}) : json(401, {});
    }));
    await Promise.all([api("/a"), api("/b"), api("/c")]);
    expect(refreshes).toBe(1);
  });

  it("reports a signed-out error when the refresh token is refused or missing", async () => {
    store.set("doorstep_token", "old");
    store.set("doorstep_refresh_token", "bad");
    vi.stubGlobal("fetch", vi.fn(async () => json(401, { detail: "Token is invalid" })));
    const err = await api("/api/auth/me/").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(isSignedOutError(err)).toBe(true);
  });

  it("never stores a refresh answer that is not token-shaped", async () => {
    store.set("doorstep_token", "old");
    store.set("doorstep_refresh_token", "r1");
    vi.stubGlobal("fetch", vi.fn(async (url: string) =>
      url === "/api/auth/refresh/" ? json(200, { access: "<script>alert(1)</script>", refresh: { not: "a string" } }) : json(401, {}),
    ));
    await expect(api("/api/bookings/")).rejects.toBeInstanceOf(ApiError);
    expect(store.get("doorstep_token")).toBe("old");
    expect(store.get("doorstep_refresh_token")).toBe("r1");
  });

  it("does not try to refresh a wrong-password answer or other errors", async () => {
    const fetchMock = vi.fn(async () => json(401, { error: "Invalid email or password." }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/api/auth/login/", { method: "POST", body: "{}" })).rejects.toThrow("Invalid email or password.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("a network failure is not a sign-out", async () => {
    store.set("doorstep_token", "t");
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const err = await api("/api/auth/me/").catch((e: unknown) => e);
    expect(isSignedOutError(err)).toBe(false);
    expect(isSignedOutError(new ApiError(500, "Server error"))).toBe(false);
  });
});
