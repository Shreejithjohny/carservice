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
  ShieldCheck,
  Sun,
  Video,
  Wallet,
  Wrench,
  Building2,
  ClipboardCheck,
  Receipt,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";

const customer = [
  { to: "/app", label: "Home", icon: LayoutGrid, end: true },
  { to: "/app/vehicles", label: "Vehicles", icon: Car },
  { to: "/app/book", label: "Book", icon: Wrench },
  { to: "/app/track", label: "Track", icon: Gauge },
  { to: "/app/estimate", label: "AI Estimate", icon: IndianRupee },
  { to: "/app/health", label: "Car Health", icon: HeartPulse },
  { to: "/app/approvals", label: "Approvals", icon: Video },
  { to: "/app/otp", label: "OTP Handover", icon: ShieldCheck },
  { to: "/app/invoices", label: "Invoices", icon: Receipt },
  { to: "/app/notifications", label: "Alerts", icon: Bell },
  { to: "/app/wallet", label: "Wallet", icon: Wallet },
];

const admin = [
  { to: "/admin", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/admin/catalog", label: "Car Catalog", icon: Layers },
  { to: "/admin/bookings", label: "Bookings", icon: Gauge },
  { to: "/admin/invoices", label: "Invoices", icon: Receipt },
  { to: "/admin/video", label: "Upload Video", icon: Video },
  { to: "/admin/discounts", label: "Discounts", icon: IndianRupee },
];

const manager = [
  { to: "/service-center", label: "Center Dashboard", icon: Building2, end: true },
  { to: "/service-center/bookings", label: "Manage Bookings", icon: Gauge },
  { to: "/service-center/invoices", label: "Invoices", icon: Receipt },
];

const mechanic = [
  { to: "/mechanic", label: "Service Jobs", icon: ClipboardCheck, end: true },
];

const driver = [
  { to: "/driver", label: "Pickup Jobs", icon: Car, end: true },
];

export function AppShell({ variant }: { variant: "customer" | "admin" | "driver" }) {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const navigate = useNavigate();

  const userRole = (user?.role || "").toLowerCase();
  let links = customer;

  if (variant === "admin") {
    if (userRole === "service_center" || userRole === "service_center_manager" || userRole === "manager") {
      links = manager;
    } else if (userRole === "mechanic") {
      links = mechanic;
    } else {
      links = admin;
    }
  } else if (variant === "driver" || userRole === "driver" || userRole === "valet") {
    links = driver;
  }

  return (
    <div className="min-h-dvh bg-[#f6f3ee] text-zinc-900 dark:bg-[#07080c] dark:text-zinc-100">
      <div className="mx-auto flex max-w-7xl">
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-1 border-r border-zinc-200/70 p-4 dark:border-zinc-800 md:flex">
          <div className="mb-4 px-2 text-xl font-extrabold tracking-tight">
            Door<span className="text-[#ff4d2e]">Step</span>
          </div>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-2xl px-3 py-2 text-sm font-medium ${
                  isActive ? "bg-[#ff4d2e] text-white" : "hover:bg-zinc-200/60 dark:hover:bg-zinc-800"
                }`
              }
            >
              <l.icon size={16} /> {l.label}
            </NavLink>
          ))}
          <div className="mt-auto space-y-2">
            <button type="button" className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm hover:bg-zinc-200/60 dark:hover:bg-zinc-800" onClick={toggle}>
              {dark ? <Sun size={16} /> : <Moon size={16} />} {dark ? "Light" : "Dark"} mode
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm text-red-600"
              onClick={() => {
                logout();
                navigate("/");
              }}
            >
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 p-4 pb-24 md:p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">{user?.role || variant}</p>
              <h1 className="text-2xl font-bold">{user?.name}</h1>
            </div>
            <img src={user?.avatarUrl || `https://api.dicebear.com/9.x/adventurer/svg?seed=${user?.name}`} alt="" className="h-11 w-11 rounded-full bg-zinc-200" />
          </div>
          <Outlet />
        </main>
      </div>
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex justify-around border-t border-zinc-200 bg-white/90 py-2 dark:border-zinc-800 dark:bg-zinc-950/90 md:hidden">
        {links.slice(0, 5).map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `flex flex-col items-center text-[10px] ${isActive ? "text-[#ff4d2e]" : "text-zinc-500"}`}>
            <l.icon size={18} />
            {l.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
