import { useId } from "react";

/**
 * The DoorStep logo: a map pin with a front door and its step inside ("service at your doorstep").
 * The same drawing is public/favicon.svg and, full-bleed, public/apple-touch-icon.png.
 */
export function LogoMark({ size = 32, className = "" }: Readonly<{ size?: number; className?: string }>) {
  // A unique gradient id per copy: several logos can be on a page, and a gradient defined inside a
  // hidden copy (e.g. the sidebar on phones) can't be used by the visible one
  const gradientId = `doorstep-logo-${useId().replaceAll(":", "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#1d4ed8" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#${gradientId})`} />
      <path d="M32 55s-17-16.1-17-28.5a17 17 0 0 1 34 0C49 38.9 32 55 32 55Z" fill="#fff" />
      <path d="M25.5 36V22.5a6.5 6.5 0 0 1 13 0V36Z" fill="#1d4ed8" />
      <circle cx="35" cy="29.5" r="1.6" fill="#fff" />
      <path d="M22.5 39h19" stroke="#1d4ed8" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

/** Logo mark with the "DoorStep" wordmark. */
export function Logo({ size = 32, className = "" }: Readonly<{ size?: number; className?: string }>) {
  return (
    <span className={`inline-flex items-center gap-2 font-extrabold tracking-tight ${className}`}>
      <LogoMark size={size} />
      <span>
        Door<span className="text-brand-fg">Step</span>
      </span>
    </span>
  );
}
