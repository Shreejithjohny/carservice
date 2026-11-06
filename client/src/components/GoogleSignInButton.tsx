import { useEffect, useRef, useState } from "react";
import { useAuth } from "../hooks/useAuth";

// Minimal typing for Google Identity Services (https://accounts.google.com/gsi/client)
type GoogleIdentity = {
  accounts: {
    id: {
      initialize(config: { client_id: string; callback: (response: { credential?: string }) => void; ux_mode?: "popup" }): void;
      renderButton(parent: HTMLElement, options: Record<string, string | number>): void;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

let scriptLoading: Promise<GoogleIdentity> | null = null;

function loadGoogleIdentity(): Promise<GoogleIdentity> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google);
  scriptLoading ??= new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => (window.google ? resolve(window.google) : reject(new Error("Google sign-in did not load")));
    script.onerror = () => {
      scriptLoading = null; // allow a retry on the next render
      reject(new Error("Google sign-in did not load"));
    };
    document.head.appendChild(script);
  });
  return scriptLoading;
}

type Props = Readonly<{
  /** Called with the ID token ("credential") once the person has picked their Google account. */
  onCredential: (credential: string) => void;
  /** Google's wording on the button. */
  text?: "signin_with" | "signup_with" | "continue_with";
}>;

/**
 * Google's official "Sign in with Google" button. Renders nothing when the backend has no
 * GOOGLE_CLIENT_ID, so the page simply shows the password form.
 */
export function GoogleSignInButton({ onCredential, text = "continue_with" }: Props) {
  const { googleClientId } = useAuth();
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    callback.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    if (!googleClientId) return;
    let cancelled = false;
    loadGoogleIdentity()
      .then((google) => {
        const el = container.current;
        if (cancelled || !el) return;
        google.accounts.id.initialize({
          client_id: googleClientId,
          ux_mode: "popup",
          callback: (response) => {
            if (response.credential) callback.current(response.credential);
          },
        });
        el.replaceChildren();
        google.accounts.id.renderButton(el, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          text,
          logo_alignment: "center",
          width: Math.min(400, Math.max(200, el.offsetWidth)), // Google allows 200-400 px
        });
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [googleClientId, text]);

  if (!googleClientId) return null;
  return (
    <div>
      <div ref={container} className="flex min-h-[44px] justify-center" data-testid="google-signin" />
      {loadFailed && (
        <p className="mt-1 text-center text-xs text-zinc-500">
          Couldn't load Google sign-in. Check your connection or ad blocker, then reload the page.
        </p>
      )}
    </div>
  );
}

/** "or" divider between the password form and the Google button. */
export function OrDivider() {
  const { googleClientId } = useAuth();
  if (!googleClientId) return null;
  return (
    <div className="flex items-center gap-3 text-xs font-semibold uppercase text-zinc-400">
      <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />
      or
      <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />
    </div>
  );
}
