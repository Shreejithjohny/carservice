import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { homePathForRole } from "../utils/roles";

export function VerifyOtp() {
  const { sendOtp, verifyOtp, bypassLogin, demoMode } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const state = (location.state as { identifier?: string; name?: string } | null) || {};
  const [identifier, setIdentifier] = useState(state.identifier || "");
  const [name, setName] = useState(state.name || "");
  const [otpCode, setOtpCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  function routeUser(user: { role: string; name?: string }) {
    navigate(homePathForRole(user.role));
  }

  // Resend cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim() || otpCode.trim().length !== 6) {
      push({ title: "Enter your email/mobile and the 6-digit code", tone: "err" });
      return;
    }

    setBusy(true);
    try {
      const user = await verifyOtp(identifier.trim(), otpCode.trim(), name.trim());
      push({ title: `Verification successful! Welcome ${user.name}` });
      routeUser(user);
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Verification failed. Please try again.",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleInstantBypass() {
    if (!identifier.trim()) {
      push({ title: "Enter an email or mobile phone number first", tone: "err" });
      return;
    }
    setBusy(true);
    try {
      const user = await bypassLogin(identifier.trim(), "customer", name.trim());
      push({ title: `Bypassed OTP! Welcome ${user.name}` });
      routeUser(user);
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Bypass failed",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleResend() {
    if (cooldown > 0) return;
    if (!identifier.trim()) {
      push({ title: "Enter an email or mobile phone number first", tone: "err" });
      return;
    }
    setBusy(true);
    try {
      const res = await sendOtp(identifier.trim());
      setCooldown(res.cooldown_seconds || 60);
      push({ title: `New OTP code sent to ${identifier}` });
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Failed to resend OTP",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-canvas px-4 py-10 dark:bg-canvas-dark dark:text-white flex items-center justify-center">
      <div className="w-full max-w-md">
        <Link to="/login" className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300">
          ← Back to sign in
        </Link>
        <h1 className="mt-4 text-3xl font-extrabold">Verify OTP</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Enter the 6-digit verification code sent to <strong className="text-zinc-800 dark:text-zinc-200">{identifier || "your email/mobile"}</strong>.
        </p>

        <form className="glass mt-6 space-y-4 rounded-3xl p-6" onSubmit={handleVerify}>
          {!state.identifier && (
            <label className="block text-xs font-semibold text-zinc-500">
              Email or Mobile Number
              <input
                required
                className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                placeholder="email@example.com or +919876543210"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </label>
          )}

          {!state.name && (
            <label className="block text-xs font-semibold text-zinc-500">
              Your Name (Optional)
              <input
                className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                placeholder="John Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
          )}

          <div className="space-y-1">
            <label className="block text-xs font-semibold text-zinc-500">6-Digit Verification Code</label>
            <input
              required
              autoFocus
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              className="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-center text-2xl font-bold tracking-[0.4em] dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-brand"
              placeholder="000000"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
            />
          </div>

          <button
            disabled={busy}
            className="w-full rounded-2xl bg-brand py-3 text-sm font-semibold text-white transition hover:bg-brand-hover disabled:opacity-50 shadow-md shadow-brand/20"
            type="submit"
          >
            {busy ? "Verifying..." : "Verify & Continue"}
          </button>

          {demoMode && (
            <button
              type="button"
              disabled={busy}
              onClick={handleInstantBypass}
              className="w-full rounded-2xl bg-zinc-200 dark:bg-zinc-800 py-2.5 text-xs font-bold text-zinc-700 dark:text-zinc-200 transition hover:bg-emerald-600 hover:text-white flex items-center justify-center gap-1.5"
            >
              ⚡ Skip OTP (demo mode)
            </button>
          )}

          <div className="flex items-center justify-between border-t border-zinc-200/70 pt-4 text-xs dark:border-zinc-700/70">
            <span className="text-zinc-500">Didn't receive code?</span>
            <button
              type="button"
              disabled={cooldown > 0 || busy}
              onClick={handleResend}
              className="font-bold text-brand-fg hover:underline disabled:text-zinc-400 disabled:no-underline"
            >
              {cooldown > 0 ? `Resend OTP in ${cooldown}s` : "Resend OTP"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
