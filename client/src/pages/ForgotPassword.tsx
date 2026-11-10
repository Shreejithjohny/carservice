import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { PasswordField, PASSWORD_HINT } from "../components/PasswordField";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
import { homePathForRole } from "../utils/roles";
import type { User } from "../types";

/**
 * "Forgot password?" without emails: sign in with the Google account that has the same email
 * address (which proves it is yours), then choose a new password. The server accepts a new password
 * without the old one for 15 minutes after a Google sign-in.
 */
export function ForgotPassword() {
  const { googleLogin, changePassword, googleClientId } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();

  const [signedIn, setSignedIn] = useState<User | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function onGoogle(credential: string) {
    setBusy(true);
    try {
      setSignedIn(await googleLogin(credential));
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Google sign-in failed", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  async function onReset(e: FormEvent) {
    e.preventDefault();
    if (!signedIn) return;
    if (password !== confirm) return push({ title: "The two passwords don't match", tone: "err" });
    setBusy(true);
    try {
      await changePassword("", password);
      push({ title: "Password updated. You're signed in." });
      void navigate(homePathForRole(signedIn.role));
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not set the password", tone: "err" });
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
        <h1 className="mt-4 text-3xl font-extrabold">Reset password</h1>

        {signedIn ? (
          <form className="glass mt-6 space-y-4 rounded-3xl p-5" onSubmit={onReset}>
            <p className="text-sm text-zinc-500">
              Signed in as <span className="font-semibold text-zinc-800 dark:text-zinc-200">{signedIn.email}</span>. Choose a new password.
            </p>
            <PasswordField label="New password" value={password} onChange={setPassword} autoComplete="new-password" hint={PASSWORD_HINT} />
            <PasswordField label="Confirm new password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
            <button disabled={busy} type="submit" className="w-full rounded-2xl bg-brand py-3 text-sm font-semibold text-white disabled:opacity-50">
              {busy ? "Saving..." : "Set new password"}
            </button>
            <button type="button" onClick={() => void navigate(homePathForRole(signedIn.role))} className="w-full text-xs font-semibold text-zinc-500 underline">
              Skip, keep my old password
            </button>
          </form>
        ) : (
          <div className="glass mt-6 space-y-4 rounded-3xl p-5">
            {googleClientId ? (
              <>
                <p className="text-sm text-zinc-500">
                  Continue with the Google account that uses the <b>same email address</b> as your DoorStep account.
                  You'll be signed in and can choose a new password.
                </p>
                <GoogleSignInButton onCredential={(credential) => void onGoogle(credential)} text="continue_with" />
              </>
            ) : (
              <p className="text-sm text-zinc-500">
                Password reset works through Google sign-in, which isn't set up on this server yet. Please contact the service center.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
