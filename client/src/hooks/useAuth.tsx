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
  sendOtp: (identifier: string, role?: Role) => Promise<SendOtpResponse>;
  verifyOtp: (identifier: string, otpCode: string, name?: string) => Promise<User>;
  bypassLogin: (identifier?: string, role?: Role, name?: string) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readUser());
  const [loading, setLoading] = useState(true);

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

  const value = useMemo<AuthCtx>(
    () => ({
      user,
      loading,
      async sendOtp(identifier, role = "customer") {
        const res = await api<SendOtpResponse>("/api/auth/send-otp/", {
          method: "POST",
          body: JSON.stringify({ identifier, role: role.toUpperCase() }),
        });
        return res;
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
    [user, loading],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
