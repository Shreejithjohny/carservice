import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../services/api";

/** What the driver sees about live location sharing. */
export type GpsStatus =
  | "off"
  | "starting" // waiting for the first GPS fix
  | "live" // positions are reaching the server
  | "denied" // location permission refused
  | "no-fix" // permission given, but the phone can't get a position right now
  | "offline" // positions can't reach the server; retrying
  | "insecure" // page not on https:// or localhost, where browsers block GPS
  | "unsupported";

const SEND_EVERY_MS = 10_000;
const STORAGE_KEY = "doorstep_gps_jobs";

function readStored(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(raw) ? raw.map(String) : [];
  } catch {
    return [];
  }
}

function store(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Private mode or storage blocked: sharing still works, it just isn't remembered after a reload
  }
}

/**
 * Shares the phone's live GPS with the customers of the jobs it is switched on for.
 * One continuous GPS watch serves all of them. A position goes out at most every 10 seconds, and
 * the last one is re-sent when the driver stands still, so the customer still sees "Live".
 * The choice survives a page reload, and the screen is kept awake while sharing (where the
 * browser supports it), because phones pause web pages when they sleep.
 *
 * `activeIds` are the jobs at a stage where sharing is allowed; others are ignored.
 */
export function useGpsSharing(activeIds: string[]) {
  const [enabled, setEnabled] = useState<string[]>(readStored);
  const [status, setStatus] = useState<GpsStatus>("off");
  const [lastSentAt, setLastSentAt] = useState<number | null>(null);
  const [screenKeptOn, setScreenKeptOn] = useState(false);
  const position = useRef<{ latitude: number; longitude: number } | null>(null);
  const lastSent = useRef(0);

  const sharing = enabled.filter((id) => activeIds.includes(id));
  const sharingKey = sharing.join(",");

  const setFor = useCallback((id: string, on: boolean) => {
    setEnabled((prev) => {
      const next = on ? [...new Set([...prev, id])] : prev.filter((x) => x !== id);
      store(next);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!sharing.length) {
      setStatus("off");
      return;
    }
    if (!globalThis.isSecureContext) {
      setStatus("insecure");
      return;
    }
    if (!("geolocation" in navigator)) {
      setStatus("unsupported");
      return;
    }
    setStatus((s) => (s === "live" ? s : "starting"));

    const send = (force = false) => {
      const at = position.current;
      if (!at || (!force && Date.now() - lastSent.current < SEND_EVERY_MS)) return;
      lastSent.current = Date.now();
      for (const id of sharing) {
        api(`/api/driver/pickups/${id}/location/`, { method: "POST", body: JSON.stringify(at) })
          .then(() => {
            setLastSentAt(Date.now());
            setStatus("live");
          })
          .catch((err) => {
            // The job moved on (e.g. completed) or isn't this driver's any more: stop sharing it
            if (err instanceof ApiError && [400, 403, 404].includes(err.status)) setFor(id, false);
            else setStatus("offline");
          });
      }
    };

    const watch = navigator.geolocation.watchPosition(
      (pos) => {
        position.current = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        send();
      },
      (err) => setStatus(err.code === err.PERMISSION_DENIED ? "denied" : "no-fix"),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 }
    );
    // Standing still gives no new GPS events: re-send the last position so the customer sees "Live"
    const heartbeat = setInterval(() => send(), SEND_EVERY_MS);

    // Keep the screen on while sharing; the browser drops the lock when the page is hidden
    let lock: WakeLockSentinel | null = null;
    const keepAwake = async () => {
      try {
        lock = (await navigator.wakeLock?.request("screen")) ?? null;
        setScreenKeptOn(!!lock);
      } catch {
        setScreenKeptOn(false);
      }
    };
    void keepAwake();
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      send(true); // back from the background: update the customer straight away
      void keepAwake();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      navigator.geolocation.clearWatch(watch);
      clearInterval(heartbeat);
      document.removeEventListener("visibilitychange", onVisible);
      void lock?.release().catch(() => undefined);
      setScreenKeptOn(false);
    };
    // Restarted only when the set of shared jobs changes
  }, [sharingKey]);

  return {
    isSharing: (id: string) => sharing.includes(id),
    start: (id: string) => setFor(id, true),
    stop: (id: string) => setFor(id, false),
    status,
    lastSentAt,
    screenKeptOn,
  };
}
