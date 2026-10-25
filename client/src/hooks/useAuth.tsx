import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User, Role } from "../types";
import { api, clearSession, readUser, saveSession } from "../services/api";

type SendOtpResponse = {
  message: string;
  identifier: string;
  cooldown_seconds: number;
  provider?: string;
};

type VerifyOtpResponse = {
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
  sendOtp: (identifier: string) => Promise<SendOtpResponse>;
  verifyOtp: (identifier: string, otpCode: string, name?: string) => Promise<User>;
  bypassLogin: (identifier?: string, role?: Role, name?: string) => Promise<User>;
  passwordLogin: (identifier: string, password: string) => Promise<User>;
  register: (details: { name: string; email: string; phone?: string; password: string }) => Promise<User>;
  requestPasswordReset: (identifier: string) => Promise<{ message: string; otp_code?: string }>;
  confirmPasswordReset: (identifier: string, otpCode: string, newPassword: string) => Promise<User>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readUser());
  const [loading, setLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    api<{ demo_login?: boolean }>("/api/health-check/")
      .then((res) => setDemoMode(Boolean(res.demo_login)))
      .catch(() => setDemoMode(false));
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
      } catch {
        clearSession();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    void boot();
  }, []);

  // Stores the tokens from any sign-in response and returns the signed-in user
  function finishSignIn(res: VerifyOtpResponse, name?: string): User {
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
      async sendOtp(identifier) {
        return api<SendOtpResponse>("/api/auth/send-otp/", {
          method: "POST",
          body: JSON.stringify({ identifier }),
        });
      },
      async verifyOtp(identifier, otpCode, name) {
        const res = await api<VerifyOtpResponse>("/api/auth/verify-otp/", {
          method: "POST",
          body: JSON.stringify({ identifier, otp_code: otpCode, name }),
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
      async bypassLogin(identifier = "customer@smartdoorstep.com", role = "customer", name) {
        const res = await api<VerifyOtpResponse>("/api/auth/bypass-login/", {
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
      async passwordLogin(identifier, password) {
        const res = await api<VerifyOtpResponse>("/api/auth/login/", {
          method: "POST",
          body: JSON.stringify({ identifier, password }),
        });
        return finishSignIn(res);
      },
      async register(details) {
        const res = await api<VerifyOtpResponse>("/api/auth/register/", {
          method: "POST",
          body: JSON.stringify(details),
        });
        return finishSignIn(res, details.name);
      },
      async requestPasswordReset(identifier) {
        return api<{ message: string; otp_code?: string }>("/api/auth/password-reset/request/", {
          method: "POST",
          body: JSON.stringify({ identifier }),
        });
      },
      async confirmPasswordReset(identifier, otpCode, newPassword) {
        const res = await api<VerifyOtpResponse>("/api/auth/password-reset/confirm/", {
          method: "POST",
          body: JSON.stringify({ identifier, otp_code: otpCode, new_password: newPassword }),
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
        } catch {
          clearSession();
          setUser(null);
        }
      },
    }),
    [user, loading, demoMode],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
