import { api } from "../services/api";
import { TOKEN_KEY } from "../types";

/** Browser alerts need a service worker, the Push API, and a secure page (https or localhost). */
export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && window.isSecureContext;
}

function keyBytes(base64Url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(base64Url.length / 4) * 4, "=");
  const raw = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  return (await registration?.pushManager.getSubscription()) ?? null;
}

/** True when this browser is subscribed (and the person hasn't blocked notifications since). */
export async function pushEnabled(): Promise<boolean> {
  if (!pushSupported() || Notification.permission !== "granted") return false;
  return (await currentSubscription()) !== null;
}

/**
 * Asks permission, subscribes this browser and tells the backend. Throws an Error with a message
 * fit to show the person when they refuse or the browser can't do it.
 */
export async function enablePush(publicKey: string): Promise<void> {
  if (!pushSupported()) throw new Error("This browser doesn't support alerts. On iPhone, add the site to your Home Screen first.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Notifications are blocked for this site. Allow them in your browser's site settings, then try again.");
  }
  const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  // A subscription made with an older server key can't receive our messages: replace it
  const wanted = keyBytes(publicKey);
  const existingKey = subscription?.options.applicationServerKey;
  if (subscription && existingKey && !sameBytes(new Uint8Array(existingKey), wanted)) {
    await subscription.unsubscribe();
    subscription = null;
  }
  try {
    subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: wanted });
  } catch {
    throw new Error("Your browser couldn't turn on alerts. Private/incognito windows don't allow them: try a normal window.");
  }
  await api("/api/push/subscription/", { method: "POST", body: JSON.stringify(subscription.toJSON()) });
}

function sameBytes(a: Uint8Array, b: Uint8Array): boolean {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

/** Stops alerts on this browser. Safe to call when not subscribed. */
export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  // Read before the first await, so this still works when the session is cleared right after the call (sign-out)
  const token = localStorage.getItem(TOKEN_KEY);
  const subscription = await currentSubscription();
  if (!subscription) return;
  await fetch("/api/push/subscription/", {
    method: "DELETE",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ endpoint: subscription.endpoint }),
    keepalive: true,
  }).catch(() => undefined);
  await subscription.unsubscribe().catch(() => undefined);
}
