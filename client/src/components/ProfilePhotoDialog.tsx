import { useRef, useState } from "react";
import { Camera, LoaderCircle, Trash2, X } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { api, ApiError } from "../services/api";
import { Avatar } from "./Avatar";

/** Add, change or remove the signed-in user's profile photo. */
export function ProfilePhotoDialog({ onClose }: Readonly<{ onClose: () => void }>) {
  const { user, refresh } = useAuth();
  const { push } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  if (!user) return null;

  async function upload(file: File) {
    const body = new FormData();
    body.append("photo", file);
    setBusy("upload");
    try {
      await api("/api/auth/avatar/", { method: "POST", body });
      await refresh();
      push({ title: "Profile photo updated" });
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not upload the photo", tone: "err" });
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("remove");
    try {
      await api("/api/auth/avatar/", { method: "DELETE" });
      await refresh();
      push({ title: "Profile photo removed" });
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not remove the photo", tone: "err" });
    } finally {
      setBusy(null);
    }
  }

  return (
    <dialog
      open
      aria-labelledby="profile-photo-title"
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center bg-black/60 p-4 text-inherit backdrop-blur-sm"
    >
      <div className="glass w-full max-w-sm space-y-5 rounded-3xl bg-white p-6 dark:bg-zinc-900">
        <div className="flex items-center justify-between">
          <h2 id="profile-photo-title" className="text-lg font-extrabold">
            Profile photo
          </h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-1 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col items-center gap-2">
          <Avatar name={user.name} url={user.avatar_url} size={112} />
          <p className="text-center text-xs text-zinc-500">
            {user.avatar_url ? "This photo is shown on your account." : "No photo yet, so your initials are shown."} Location data in photos is removed.
          </p>
        </div>

        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label="Choose a profile photo"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = ""; // choosing the same file again still triggers a change
            if (file) void upload(file);
          }}
        />
        <div className="grid gap-2">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => fileInput.current?.click()}
            className="flex items-center justify-center gap-2 rounded-2xl bg-brand py-2.5 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
          >
            {busy === "upload" ? <LoaderCircle size={16} className="animate-spin" /> : <Camera size={16} />}
            {user.avatar_url ? "Change photo" : "Upload photo"}
          </button>
          {user.avatar_url && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void remove()}
              className="flex items-center justify-center gap-2 rounded-2xl border border-zinc-200 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-red-950/30"
            >
              {busy === "remove" ? <LoaderCircle size={16} className="animate-spin" /> : <Trash2 size={16} />} Remove photo
            </button>
          )}
        </div>
      </div>
    </dialog>
  );
}
