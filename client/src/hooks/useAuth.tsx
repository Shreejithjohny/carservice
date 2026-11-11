import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User, Role } from "../types";
import { api, clearSession, isSignedOutError, readUser, saveSession } from "../services/api";
import { disablePush } from "../utils/push";

type SignInResponse = {
  message: string;
  token: string;
  access?: string;
  refresh?: string;
  user: User;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  /** True only when the backend has OTP_BYPASS on (local demo); hides demo logins otherwise. */
  demoMode: boolean;
  /** OAuth client ID for "Sign in with Google"; null when the backend has none (button hidden). */
  googleClientId: string | null;
  bypassLogin: (identifier?: string, role?: Role, name?: string) => Promise<User>;
  /** `role` is the sign-in tab used (e.g. "driver"); the server refuses accounts of another role. */
  passwordLogin: (identifier: string, password: string, role?: Role) => Promise<User>;
  register: (details: { name: string; email: string; phone?: string; password: string }) => Promise<User>;
  /** `credential` is the ID token from Google's button; `role` is the sign-in tab used. */
  googleLogin: (credential: string, role?: Role) => Promise<User>;
  /** `currentPassword` may be empty for accounts without one, or just after signing in with Google. */
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [user, setUser] = useState<User | null>(readUser());
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);

  // Ask the backend whether demo sign-in is on (and for the Google client ID). When the page opens before the backend has
  // started (common with `npm run dev`), keep asking every 3 seconds for up to 2 minutes instead
  // of hiding the demo buttons for good.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = async (attempt: number) => {
      try {
        const res = await api<{ demo_login?: boolean; google_client_id?: string | null }>("/api/health-check/");
        if (!stopped) {
          setDemoMode(Boolean(res.demo_login));
          setGoogleClientId(res.google_client_id || null);
        }
      } catch {
        if (!stopped && attempt < 40) timer = setTimeout(check, 3000, attempt + 1);
      }
    };
    void check(1);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const boot = async () => {
      try {
        if (localStorage.getItem("doorstep_token")) {
          const me = await api<User>("/api/auth/me/");
          const normalized: User = {
            ...me,
            role: (me.role.toLowerCase() as Role),
            name: me.name || me.email?.split("@")[0] || me.phone || "User",
          };
          setUser(normalized);
          localStorage.setItem("doorstep_user", JSON.stringify(normalized));
        }
      } catch (err) {
        // Sign out only when the server rejects the session. A request cut short (a quick reload,
        // no connection, the backend restarting) keeps the stored session.
        if (isSignedOutError(err)) {
          clearSession();
          setUser(null);
        }
      } finally {
        setLoading(false);
      }
    };
    void boot();
  }, []);

  // Stores the tokens from any sign-in response and returns the signed-in user
  function finishSignIn(res: SignInResponse, name?: string): User {
    const accessToken = res.access || res.token;
    saveSession(accessToken, res.user, res.refresh);
    const normalizedUser: User = {
      ...res.user,
      role: res.user.role.toLowerCase() as Role,
      name: res.user.name || name || res.user.email?.split("@")[0] || "User",
    };
    setUser(normalizedUser);
    return normalizedUser;
  }

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      loading,
      demoMode,
      googleClientId,
      async bypassLogin(identifier = "customer@smartdoorstep.com", role = "customer", name) {
        const res = await api<SignInResponse>("/api/auth/bypass-login/", {
          method: "POST",
          body: JSON.stringify({ identifier, role: role.toUpperCase(), name }),
        });
        const accessToken = res.access || res.token;
        saveSession(accessToken, res.user, res.refresh);
        const normalizedUser: User = {
          ...res.user,
          role: (res.user.role.toLowerCase() as Role),
          name: res.user.name || name || res.user.email?.split("@")[0] || "User",
        };
        setUser(normalizedUser);
        return normalizedUser;
      },
      async passwordLogin(identifier, password, role) {
        const res = await api<SignInResponse>("/api/auth/login/", {
          method: "POST",
          body: JSON.stringify({ identifier, password, role: role?.toUpperCase() }),
        });
        return finishSignIn(res);
      },
      async register(details) {
        const res = await api<SignInResponse>("/api/auth/register/", {
          method: "POST",
          body: JSON.stringify(details),
        });
        return finishSignIn(res, details.name);
      },
      async googleLogin(credential, role) {
        const res = await api<SignInResponse>("/api/auth/google/", {
          method: "POST",
          body: JSON.stringify({ credential, role: role?.toUpperCase() }),
        });
        return finishSignIn(res);
      },
      async changePassword(currentPassword, newPassword) {
        const res = await api<{ user: User }>("/api/auth/change-password/", {
          method: "POST",
          body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        });
        if (user) setUser({ ...user, has_password: res.user.has_password });
      },
      logout() {
        // Stop alerts for this account on this browser (the next person to sign in here may differ).
        // Not awaited: it reads the token before the session is cleared below.
        void disablePush().catch(() => undefined);
        clearSession();
        setUser(null);
      },
      async refresh() {
        try {
          const me = await api<User>("/api/auth/me/");
          const normalized: User = {
            ...me,
            role: (me.role.toLowerCase() as Role),
            name: me.name || me.email?.split("@")[0] || me.phone || "User",
          };
          setUser(normalized);
        } catch (err) {
          if (isSignedOutError(err)) {
            clearSession();
            setUser(null);
          }
        }
      },
    }),
    [user, loading, demoMode, googleClientId],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
