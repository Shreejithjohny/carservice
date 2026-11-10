import { useEffect, useState } from "react";
import { Bell, BellRing } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useToast } from "../hooks/useToast";
import { disablePush, enablePush, pushEnabled, pushSupported } from "../utils/push";

/**
 * Header button that turns browser alerts on or off for this device. Hidden when the backend has
 * no push keys or the browser can't receive pushes.
 */
export function PushToggle() {
  const { data: health } = useApi<{ push_public_key?: string | null }>("/api/health-check/");
  const { push } = useToast();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const publicKey = health?.push_public_key || "";

  useEffect(() => {
    void pushEnabled().then(setEnabled).catch(() => setEnabled(false));
  }, []);

  if (!publicKey || !pushSupported()) return null;

  async function toggle() {
    setBusy(true);
    try {
      if (enabled) {
        await disablePush();
        setEnabled(false);
        push({ title: "Alerts turned off on this device" });
      } else {
        await enablePush(publicKey);
        setEnabled(true);
        push({ title: "Alerts are on. You'll be notified even when this site is closed." });
      }
    } catch (err) {
      push({ title: err instanceof Error ? err.message : "Could not change alerts", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  const label = enabled ? "Turn off alerts on this device" : "Get alerts on this device";
  return (
    <button
      type="button"
      onClick={() => void toggle()}
      disabled={busy}
      title={label}
      aria-label={label}
      aria-pressed={enabled}
      className={`rounded-full p-2 hover:bg-zinc-200/60 disabled:opacity-50 dark:hover:bg-zinc-800 ${enabled ? "text-brand-fg" : "text-zinc-500"}`}
    >
      {enabled ? <BellRing size={18} /> : <Bell size={18} />}
    </button>
  );
}
