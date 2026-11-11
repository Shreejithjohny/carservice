import { Link } from "react-router-dom";
import { useSite } from "../siteInfo";

export const LEGAL_LINKS = [
  { to: "/privacy", label: "Privacy" },
  { to: "/terms", label: "Terms" },
  { to: "/refunds", label: "Refunds & cancellation" },
  { to: "/contact", label: "Contact" },
] as const;

/** Links to the legal pages, for the public pages (landing, sign-in, register). */
export function SiteFooter({ className = "" }: Readonly<{ className?: string }>) {
  const SITE = useSite();
  return (
    <footer className={`flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs ${className}`}>
      <span>© {new Date().getFullYear()} {SITE.name}</span>
      {LEGAL_LINKS.map((link) => (
        <Link key={link.to} to={link.to} className="underline-offset-2 hover:underline">
          {link.label}
        </Link>
      ))}
    </footer>
  );
}
