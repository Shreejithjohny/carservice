import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Bell,
  Car,
  Gauge,
  HeartPulse,
  IndianRupee,
  Layers,
  LayoutGrid,
  LogOut,
  Moon,
  Sun,
  Video,
  Wrench,
  Building2,
  ClipboardCheck,
  Receipt,
  BarChart3,
  Languages,
  KeyRound,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import type { Role } from "../types";
import { useLanguage } from "../hooks/useLanguage";
import { ChangePasswordDialog } from "../components/ChangePasswordDialog";
import { LANGUAGES, type Language, type StringKey } from "../i18n/strings";

interface NavItem {
  to: string;
  label: string;
  labelKey?: StringKey;
  icon: typeof Car;
  end?: boolean;
}

// Customer screens are translated (labelKey); staff screens stay in English.
const customer: NavItem[] = [
  { to: "/app", label: "Home", labelKey: "nav.home", icon: LayoutGrid, end: true },
  { to: "/app/vehicles", label: "Vehicles", labelKey: "nav.vehicles", icon: Car },
  { to: "/app/book", label: "Book", labelKey: "nav.book", icon: Wrench },
  { to: "/app/track", label: "Track", labelKey: "nav.track", icon: Gauge },
  { to: "/app/estimate", label: "Cost Estimate", labelKey: "nav.estimate", icon: IndianRupee },
  { to: "/app/health", label: "Car Health", labelKey: "nav.health", icon: HeartPulse },
  { to: "/app/approvals", label: "Approvals", labelKey: "nav.approvals", icon: Video },
  { to: "/app/invoices", label: "Invoices", labelKey: "nav.invoices", icon: Receipt },
  { to: "/app/notifications", label: "Alerts", labelKey: "nav.alerts", icon: Bell },
];

const admin = [
  { to: "/admin", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/admin/catalog", label: "Car Catalog", icon: Layers },
  { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/admin/bookings", label: "Bookings", icon: Gauge },
  { to: "/admin/invoices", label: "Invoices", icon: Receipt },
];

const manager = [
  { to: "/service-center", label: "Center Dashboard", icon: Building2, end: true },
  { to: "/service-center/bookings", label: "Manage Bookings", icon: Gauge },
  { to: "/service-center/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/service-center/invoices", label: "Invoices", icon: Receipt },
];

const mechanic = [
  { to: "/mechanic", label: "Service Jobs", icon: ClipboardCheck, end: true },
];

const driver = [
  { to: "/driver", label: "Pickup Jobs", icon: Car, end: true },
];

const linksByRole: Record<Role, NavItem[]> = { customer, admin, service_center_manager: manager, mechanic, driver };

export function AppShell() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const { lang, setLang, t } = useLanguage();
  const navigate = useNavigate();
  const [changingPassword, setChangingPassword] = useState(false);
  const isCustomer = user?.role.toLowerCase() === "customer";
  const label = (l: NavItem) => (isCustomer && l.labelKey ? t(l.labelKey) : l.label);

  const links = user ? linksByRole[user.role.toLowerCase() as Role] ?? customer : customer;

  return (
    <div className="min-h-dvh bg-canvas text-zinc-900 dark:bg-canvas-dark dark:text-zinc-100">
      <div className="mx-auto flex max-w-7xl">
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-1 border-r border-zinc-200/70 p-4 dark:border-zinc-800 md:flex">
          <div className="mb-4 px-2 text-xl font-extrabold tracking-tight">
            Door<span className="text-brand-fg">Step</span>
          </div>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-2xl px-3 py-2 text-sm font-medium ${
                  isActive ? "bg-brand text-white" : "hover:bg-zinc-200/60 dark:hover:bg-zinc-800"
                }`
              }
            >
              <l.icon size={16} /> {label(l)}
            </NavLink>
          ))}
          <div className="mt-auto space-y-2">
            <button type="button" className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm hover:bg-zinc-200/60 dark:hover:bg-zinc-800" onClick={toggle}>
              {dark ? <Sun size={16} /> : <Moon size={16} />} {isCustomer ? t(dark ? "shell.light" : "shell.dark") : `${dark ? "Light" : "Dark"} mode`}
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm text-red-600"
              onClick={() => {
                logout();
                navigate("/");
              }}
            >
              <LogOut size={16} /> {isCustomer ? t("shell.signOut") : "Sign out"}
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 p-4 pb-24 md:p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">{user?.role.replace(/_/g, " ")}</p>
              <h1 className="text-2xl font-bold">{user?.name}</h1>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setChangingPassword(true)}
                title={isCustomer ? t("shell.password") : "Change password"}
                aria-label={isCustomer ? t("shell.password") : "Change password"}
                className="rounded-full p-2 text-zinc-500 hover:bg-zinc-200/60 dark:hover:bg-zinc-800"
              >
                <KeyRound size={18} />
              </button>
              {isCustomer && (
                <label className="flex items-center gap-1 text-xs text-zinc-500">
                  <Languages size={16} aria-hidden />
                  <span className="sr-only">{t("shell.language")}</span>
                  <select
                    className="rounded-xl border border-zinc-200 bg-transparent px-2 py-1 text-xs font-semibold dark:border-zinc-700 dark:bg-zinc-900"
                    value={lang}
                    onChange={(e) => setLang(e.target.value as Language)}
                  >
                    {(Object.keys(LANGUAGES) as Language[]).map((code) => (
                      <option key={code} value={code}>
                        {LANGUAGES[code]["lang.name"]}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <img src={user?.avatarUrl || `https://api.dicebear.com/9.x/adventurer/svg?seed=${user?.name}`} alt="" className="h-11 w-11 rounded-full bg-zinc-200" />
            </div>
          </div>
          <Outlet />
        </main>
      </div>
      {changingPassword && <ChangePasswordDialog onClose={() => setChangingPassword(false)} />}
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex justify-around border-t border-zinc-200 bg-white/90 py-2 dark:border-zinc-800 dark:bg-zinc-950/90 md:hidden">
        {links.slice(0, 5).map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `flex flex-col items-center text-[10px] ${isActive ? "text-brand-fg" : "text-zinc-500"}`}>
            <l.icon size={18} />
            {label(l)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
