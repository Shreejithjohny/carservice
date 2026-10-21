import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";

export function Register() {
  const { sendOtp, bypassLogin } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [busy, setBusy] = useState(false);

  async function onDirectRegister(e: FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) {
      push({ title: "Enter your full name", tone: "err" });
      return;
    }
    if (!identifier.trim()) {
      push({ title: "Enter a valid email address or mobile phone number", tone: "err" });
      return;
    }

    setBusy(true);
    try {
      const user = await bypassLogin(identifier.trim(), "customer", name.trim());
      push({ title: `Welcome to DoorStep, ${user.name}!` });
      navigate("/app");
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Registration failed",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  }

  async function onSendOtp() {
    if (name.trim().length < 2) {
      push({ title: "Enter your full name first", tone: "err" });
      return;
    }
    if (!identifier.trim()) {
      push({ title: "Enter an email or mobile phone number", tone: "err" });
      return;
    }

    setBusy(true);
    try {
      const res = await sendOtp(identifier.trim(), "customer");
      push({ title: res.message || `Verification code sent to ${identifier}` });
      navigate("/verify-otp", {
        state: { identifier: identifier.trim(), name: name.trim(), role: "customer" },
      });
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Could not request registration OTP",
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
        <h1 className="mt-4 text-3xl font-extrabold">Create account</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Register with your email or mobile phone to book doorstep vehicle services.
        </p>

        <form className="glass mt-6 space-y-4 rounded-3xl p-5" onSubmit={onDirectRegister}>
          <label className="block text-xs font-semibold text-zinc-500">
            Full Name
            <input
              required
              className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]"
              placeholder="John Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>

          <label className="block text-xs font-semibold text-zinc-500">
            Email address or Mobile phone
            <input
              required
              className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]"
              placeholder="user@example.com or +919876543210"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
          </label>

          <button
            disabled={busy}
            className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white transition hover:bg-[#e94529] disabled:opacity-50 shadow-md shadow-[#ff4d2e]/20"
            type="submit"
          >
            {busy ? "Creating account..." : "Register & Start (Bypass OTP)"}
          </button>

          <div className="pt-1 text-center">
            <button
              type="button"
              disabled={busy}
              onClick={onSendOtp}
              className="text-xs font-semibold text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300 underline"
            >
              Test with SMS/Email OTP code →
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
