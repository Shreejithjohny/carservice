import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { PasswordField, PASSWORD_HINT } from "../components/PasswordField";

const INPUT =
  "mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]";

export function Register() {
  const { register, sendOtp } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function onRegister(e: FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) return push({ title: "Enter your full name", tone: "err" });
    if (password !== confirm) return push({ title: "The two passwords don't match", tone: "err" });

    setBusy(true);
    try {
      const user = await register({ name: name.trim(), email: email.trim(), phone: phone.trim(), password });
      push({ title: `Welcome to DoorStep, ${user.name}!` });
      void navigate("/app");
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Registration failed", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  // Alternative: create the account with a one-time code instead of a password
  async function onUseOtp() {
    if (name.trim().length < 2 || !email.trim()) {
      return push({ title: "Enter your name and email first", tone: "err" });
    }
    setBusy(true);
    try {
      const res = await sendOtp(email.trim());
      push({ title: res.message || `Verification code sent to ${email}` });
      void navigate("/verify-otp", { state: { identifier: email.trim(), name: name.trim() } });
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not send the code", tone: "err" });
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
        <h1 className="mt-4 text-3xl font-extrabold">Create account</h1>
        <p className="mt-1 text-sm text-zinc-500">Register to book doorstep vehicle services.</p>

        <form className="glass mt-6 space-y-4 rounded-3xl p-5" onSubmit={onRegister}>
          <label className="block text-xs font-semibold text-zinc-500">
            <span>Full Name</span>
            <input required autoComplete="name" className={INPUT} placeholder="Meera Iyer" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block text-xs font-semibold text-zinc-500">
            Email address
            <input
              required
              type="email"
              autoComplete="email"
              className={INPUT}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block text-xs font-semibold text-zinc-500">
            Mobile number (optional)
            <input
              type="tel"
              autoComplete="tel"
              className={INPUT}
              placeholder="+91 98450 12345"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </label>
          <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="new-password" hint={PASSWORD_HINT} />
          <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} autoComplete="new-password" />

          <button
            disabled={busy}
            className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white transition hover:bg-[#e94529] disabled:opacity-50 shadow-md shadow-[#ff4d2e]/20"
            type="submit"
          >
            {busy ? "Please wait..." : "Create account"}
          </button>
          <div className="text-center">
            <button
              type="button"
              disabled={busy}
              onClick={() => void onUseOtp()}
              className="text-xs font-semibold text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-300"
            >
              Register with a one-time code instead
            </button>
          </div>
        </form>

        <p className="mt-4 text-center text-sm text-zinc-500">
          Already registered?{" "}
          <Link to="/login" className="font-semibold text-[#ff4d2e] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
