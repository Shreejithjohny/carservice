import { useState } from "react";

// Background colours for initials; each gives white text a contrast of at least 4.5:1
const COLORS = ["#2563eb", "#047857", "#7c3aed", "#e11d48", "#b45309", "#0f766e", "#4f46e5", "#475569"];

export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

/** The same name always gets the same colour. */
export function colorFor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + (ch.codePointAt(0) ?? 0)) % 1_000_003;
  return COLORS[hash % COLORS.length];
}

/**
 * A person's profile photo, or their initials on a colour picked from their name when they have
 * no photo (or it fails to load) — the way most apps show people without a picture.
 */
export function Avatar({ name, url, size = 44, className = "" }: Readonly<{ name: string; url?: string | null; size?: number; className?: string }>) {
  const [failed, setFailed] = useState<string | null>(null);
  const showPhoto = url && failed !== url;
  const style = { width: size, height: size };
  if (showPhoto) {
    return <img src={url} alt="" style={style} className={`shrink-0 rounded-full object-cover ${className}`} onError={() => setFailed(url)} />;
  }
  return (
    <span
      aria-hidden="true"
      style={{ ...style, backgroundColor: colorFor(name), fontSize: Math.round(size * 0.38) }}
      className={`grid shrink-0 select-none place-items-center rounded-full font-bold text-white ${className}`}
    >
      {initialsOf(name)}
    </span>
  );
}
