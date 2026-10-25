import { FormEvent, useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { PasswordField, PASSWORD_HINT } from "./PasswordField";

/** Change (or, for accounts created with a one-time code, first set) the signed-in user's password. */
export function ChangePasswordDialog({ onClose }: Readonly<{ onClose: () => void }>) {
  const { user, changePassword } = useAuth();
  const { push } = useToast();
  const hasPassword = user?.has_password !== false;
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return push({ title: "The two passwords don't match", tone: "err" });
    setBusy(true);
    try {
      await changePassword(current, password);
      push({ title: hasPassword ? "Password changed" : "Password set. You can now sign in with it." });
      onClose();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not change the password", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      open
      aria-labelledby="change-password-title"
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center bg-black/60 p-4 text-inherit backdrop-blur-sm"
    >
      <form className="glass w-full max-w-sm space-y-4 rounded-3xl bg-white p-6 dark:bg-zinc-900" onSubmit={onSubmit}>
        <div className="flex items-center justify-between">
          <h2 id="change-password-title" className="text-lg font-extrabold">{hasPassword ? "Change password" : "Set a password"}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-1 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800">
            <X size={18} />
          </button>
        </div>
        {hasPassword && <PasswordField label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" />}
        <PasswordField label="New password" value={password} onChange={setPassword} autoComplete="new-password" hint={PASSWORD_HINT} />
        <PasswordField label="Confirm new password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        <button disabled={busy} type="submit" className="w-full rounded-2xl bg-[#ff4d2e] py-2.5 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Saving..." : "Save password"}
        </button>
      </form>
    </dialog>
  );
}
