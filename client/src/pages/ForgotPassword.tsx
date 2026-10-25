import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { PasswordField, PASSWORD_HINT } from "../components/PasswordField";
import { homePathForRole } from "../utils/roles";

const INPUT =
  "mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]";

/** Step 1: send a reset code by email/SMS. Step 2: enter the code and a new password. */
export function ForgotPassword() {
  const { requestPasswordReset, confirmPasswordReset } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const [identifier, setIdentifier] = useState((location.state as { identifier?: string } | null)?.identifier ?? "");
  const [codeSent, setCodeSent] = useState(false);
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await requestPasswordReset(identifier.trim());
      push({ title: res.message });
      setDemoCode(res.otp_code ?? null);
      setCodeSent(true);
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not send the code", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  async function onReset(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return push({ title: "The two passwords don't match", tone: "err" });
    setBusy(true);
    try {
      const user = await confirmPasswordReset(identifier.trim(), code.trim(), password);
      push({ title: "Password updated. You're signed in." });
      void navigate(homePathForRole(user.role));
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not reset the password", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-[#f6f3ee] px-4 py-10 dark:bg-[#07080c] dark:text-white flex items-center justify-center">
      <div className="w-full max-w-md">
        <Link to="/login" className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300">
          ← Back to sign in
        </Link>
        <h1 className="mt-4 text-3xl font-extrabold">Reset password</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {codeSent ? `Enter the 6-digit code we sent to ${identifier} and choose a new password.` : "We'll send a 6-digit reset code to your email or mobile."}
        </p>

        {!codeSent ? (
          <form className="glass mt-6 space-y-4 rounded-3xl p-5" onSubmit={onRequest}>
            <label className="block text-xs font-semibold text-zinc-500">
              Email address or Mobile number
              <input required autoComplete="username" className={INPUT} value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
            </label>
            <button disabled={busy} type="submit" className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white disabled:opacity-50">
              {busy ? "Sending..." : "Send reset code"}
            </button>
          </form>
        ) : (
          <form className="glass mt-6 space-y-4 rounded-3xl p-5" onSubmit={onReset}>
            <label className="block text-xs font-semibold text-zinc-500">
              Reset code
              <input
                required
                inputMode="numeric"
                maxLength={6}
                autoComplete="one-time-code"
                className={`${INPUT} text-center font-mono text-xl tracking-[0.4em]`}
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            {demoCode && <p className="rounded-xl bg-zinc-100 p-2 text-center text-xs dark:bg-zinc-800">Demo mode: your code is {demoCode}</p>}
            <PasswordField label="New password" value={password} onChange={setPassword} autoComplete="new-password" hint={PASSWORD_HINT} />
            <PasswordField label="Confirm new password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
            <button disabled={busy} type="submit" className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white disabled:opacity-50">
              {busy ? "Saving..." : "Set new password"}
            </button>
            <button type="button" onClick={() => setCodeSent(false)} className="w-full text-xs font-semibold text-zinc-500 underline">
              Didn't get a code? Send again
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
