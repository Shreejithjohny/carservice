import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import type { Role } from "../types";
import { ROLE_LABELS, homePathForRole } from "../utils/roles";
import { Sparkles, Shield, Car, Wrench, Building2, Truck } from "lucide-react";
import { PasswordField } from "../components/PasswordField";

export function Login() {
  const { sendOtp, bypassLogin, passwordLogin, demoMode } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("customer");
  const [busy, setBusy] = useState(false);

  function redirectForRole(targetRole: string) {
    navigate(homePathForRole(targetRole));
  }

  // 1-Click Fast Login for any role
  async function handleQuickLogin(roleKey: Role, email: string) {
    setBusy(true);
    try {
      const user = await bypassLogin(email, roleKey);
      push({ title: `Signed in as ${user.name} (${user.role})` });
      redirectForRole(user.role);
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Failed to sign in",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  // Demo mode only: sign in (or create a demo account) without OTP
  async function onDirectLogin(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim()) {
      push({ title: "Enter your email or mobile phone number", tone: "err" });
      return;
    }

    setBusy(true);
    try {
      const user = await bypassLogin(identifier.trim(), role);
      push({ title: `Signed in successfully as ${user.name}!` });
      redirectForRole(user.role);
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Sign in failed",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  async function onPasswordLogin(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await passwordLogin(identifier.trim(), password);
      push({ title: `Welcome back, ${user.name}!` });
      redirectForRole(user.role);
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Sign in failed", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  async function onSendOtp(e?: FormEvent) {
    e?.preventDefault();
    if (!identifier.trim()) {
      push({ title: "Enter your email or mobile phone number first", tone: "err" });
      return;
    }

    setBusy(true);
    try {
      const res = await sendOtp(identifier.trim());
      push({ title: res.message || `Verification code sent to ${identifier}` });
      navigate("/verify-otp", { state: { identifier: identifier.trim() } });
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Failed to send OTP",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-[#f6f3ee] px-4 py-10 dark:bg-[#07080c] dark:text-white flex items-center justify-center">
      <div className="w-full max-w-md">
        <Link to="/" className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300">
          ← Back to DoorStep
        </Link>
        <h1 className="mt-4 text-3xl font-extrabold">Sign in</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Sign in with your email (or mobile number) and password.
        </p>

        <form className="glass mt-5 space-y-4 rounded-3xl p-5" onSubmit={onPasswordLogin}>
          <label className="block text-xs font-semibold text-zinc-500">
            Email address or Mobile number
            <input
              required
              autoComplete="username"
              className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]"
              placeholder="user@example.com or +919876543210"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
          </label>
          <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="current-password" />
          <button
            disabled={busy}
            className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white transition hover:bg-[#e94529] disabled:opacity-50 shadow-md shadow-[#ff4d2e]/20"
            type="submit"
          >
            {busy ? "Please wait..." : "Sign in"}
          </button>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold">
            <Link to="/forgot-password" state={{ identifier }} className="text-[#ff4d2e] hover:underline">
              Forgot password?
            </Link>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onSendOtp()}
              className="text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-300"
            >
              Sign in with a one-time code instead
            </button>
          </div>
        </form>

        {/* 1-Click Role Switcher (demo mode only) */}
        {demoMode && (
          <div className="glass mt-5 rounded-3xl p-4 border border-[#ff4d2e]/30 bg-white/60 dark:bg-zinc-900/60 shadow-sm">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#ff4d2e] mb-3">
              <Sparkles size={15} /> 1-Click Quick Demo Login
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("customer", "customer@smartdoorstep.com")}
                className="flex items-center gap-2 rounded-2xl bg-zinc-100 dark:bg-zinc-800 p-2.5 text-left text-xs font-semibold text-zinc-800 dark:text-zinc-100 hover:bg-[#ff4d2e] hover:text-white transition group disabled:opacity-50"
              >
                <Car size={16} className="text-[#ff4d2e] group-hover:text-white shrink-0" />
                <div>
                  <p className="font-bold">Customer</p>
                  <p className="text-[10px] text-zinc-400 group-hover:text-white/80">Rahul (Bookings)</p>
                </div>
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("admin", "admin@smartdoorstep.com")}
                className="flex items-center gap-2 rounded-2xl bg-zinc-100 dark:bg-zinc-800 p-2.5 text-left text-xs font-semibold text-zinc-800 dark:text-zinc-100 hover:bg-[#ff4d2e] hover:text-white transition group disabled:opacity-50"
              >
                <Shield size={16} className="text-[#ff4d2e] group-hover:text-white shrink-0" />
                <div>
                  <p className="font-bold">Admin</p>
                  <p className="text-[10px] text-zinc-400 group-hover:text-white/80">Catalog & Stats</p>
                </div>
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("driver", "driver@smartdoorstep.com")}
                className="flex items-center gap-2 rounded-2xl bg-zinc-100 dark:bg-zinc-800 p-2.5 text-left text-xs font-semibold text-zinc-800 dark:text-zinc-100 hover:bg-[#ff4d2e] hover:text-white transition group disabled:opacity-50"
              >
                <Truck size={16} className="text-[#ff4d2e] group-hover:text-white shrink-0" />
                <div>
                  <p className="font-bold">Valet / Driver</p>
                  <p className="text-[10px] text-zinc-400 group-hover:text-white/80">Pickups & GPS</p>
                </div>
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={() => handleQuickLogin("mechanic", "mechanic@smartdoorstep.com")}
                className="flex items-center gap-2 rounded-2xl bg-zinc-100 dark:bg-zinc-800 p-2.5 text-left text-xs font-semibold text-zinc-800 dark:text-zinc-100 hover:bg-[#ff4d2e] hover:text-white transition group disabled:opacity-50"
              >
                <Wrench size={16} className="text-[#ff4d2e] group-hover:text-white shrink-0" />
                <div>
                  <p className="font-bold">Mechanic</p>
                  <p className="text-[10px] text-zinc-400 group-hover:text-white/80">Inspection & Job</p>
                </div>
              </button>
            </div>

            <button
              type="button"
              disabled={busy}
              onClick={() => handleQuickLogin("service_center_manager", "manager@smartdoorstep.com")}
              className="mt-2 w-full flex items-center justify-center gap-2 rounded-2xl bg-zinc-100 dark:bg-zinc-800 p-2 text-xs font-semibold text-zinc-800 dark:text-zinc-100 hover:bg-[#ff4d2e] hover:text-white transition group disabled:opacity-50"
            >
              <Building2 size={15} className="text-[#ff4d2e] group-hover:text-white" />
              <span>Service Center Manager Dashboard</span>
            </button>
          </div>
        )}

        {demoMode && (
          <details className="mt-4 rounded-3xl border border-zinc-200 p-4 dark:border-zinc-800">
            <summary className="cursor-pointer text-xs font-semibold text-zinc-500">Demo: sign in as any role without a password</summary>
            <div className="mt-3 flex flex-wrap gap-2">
              {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRole(r)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider transition ${
                    role === r ? "bg-[#ff4d2e] text-white" : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                  }`}
                >
                  {ROLE_LABELS[r]}
                </button>
              ))}
            </div>
            <form className="mt-3 space-y-3" onSubmit={onDirectLogin}>
              <input
                required
                aria-label="Demo account email or mobile number"
                className="w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                placeholder="any-email@example.com"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
              <button
                disabled={busy}
                type="submit"
                className="w-full rounded-2xl border border-[#ff4d2e] py-2.5 text-xs font-semibold text-[#ff4d2e] disabled:opacity-50"
              >
                Demo sign in as {ROLE_LABELS[role]} (no password)
              </button>
            </form>
          </details>
        )}

        <p className="mt-4 text-center text-sm text-zinc-500">
          New here?{" "}
          <Link to="/register" className="font-semibold text-[#ff4d2e] hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

