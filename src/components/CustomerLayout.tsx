import { useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  Bot,
  Car,
  CircleHelp,
  ClipboardList,
  Gauge,
  History,
  IndianRupee,
  LayoutDashboard,
  Menu,
  Route as RouteIcon,
  UserRound,
  X,
} from "lucide-react";
import { useApp } from "../context";
import { AskAI } from "./AskAI";

const links = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/vehicles", label: "My Vehicles", icon: Car },
  { to: "/app/book", label: "Book Service", icon: ClipboardList },
  { to: "/app/estimate", label: "AI Cost Estimator", icon: IndianRupee },
  { to: "/app/track", label: "Track Service", icon: RouteIcon },
  { to: "/app/history", label: "Service History", icon: History },
  { to: "/app/help", label: "AI Help & Support", icon: CircleHelp },
  { to: "/app/notifications", label: "Notifications", icon: Bell },
  { to: "/app/profile", label: "Profile", icon: UserRound },
];

export function CustomerLayout() {
  const { user, notifications, logout } = useApp();
  const unread = notifications.filter((n) => !n.read).length;
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const title = useMemo(() => {
    const hit = links.find((l) =>
      l.end ? location.pathname === l.to : location.pathname.startsWith(l.to),
    );
    return hit?.label ?? "Customer Dashboard";
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">A</div>
          <div>
            <strong>AutoCare</strong>
            <div style={{ fontSize: 12, opacity: 0.7 }}>Doorstep service</div>
          </div>
          <button className="btn btn-ghost menu-btn" style={{ marginLeft: "auto", color: "#fff", borderColor: "transparent" }} onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
        </div>
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.end}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            onClick={() => setOpen(false)}
          >
            <l.icon size={18} />
            {l.label}
            {l.to.includes("notifications") && unread > 0 && <span className="badge">{unread}</span>}
          </NavLink>
        ))}
        <div className="sidebar-foot">
          <div style={{ fontWeight: 700 }}>{user?.name}</div>
          <div style={{ fontSize: 12, opacity: 0.75 }}>{user?.phone}</div>
          <button className="btn btn-gold" style={{ marginTop: 10, width: "100%" }} onClick={() => { logout(); navigate("/"); }}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div>
            <button className="btn btn-ghost menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">
              <Menu size={18} /> Menu
            </button>
            <div className="page-kicker">Customer</div>
            <h1 className="page-title display">{title}</h1>
          </div>
          <button className="btn btn-ghost" onClick={() => navigate("/app/notifications")}>
            <Bell size={18} /> {unread > 0 ? `${unread} new` : "Alerts"}
          </button>
        </div>
        <Outlet />
      </div>
      <nav className="mobile-nav">
        <NavLink to="/app" end className={({ isActive }) => (isActive ? "on" : "")}>
          <Gauge size={18} /> Home
        </NavLink>
        <NavLink to="/app/book" className={({ isActive }) => (isActive ? "on" : "")}>
          <ClipboardList size={18} /> Book
        </NavLink>
        <NavLink to="/app/estimate" className={({ isActive }) => (isActive ? "on" : "")}>
          <IndianRupee size={18} /> Estimate
        </NavLink>
        <NavLink to="/app/track" className={({ isActive }) => (isActive ? "on" : "")}>
          <RouteIcon size={18} /> Track
        </NavLink>
        <NavLink to="/app/help" className={({ isActive }) => (isActive ? "on" : "")}>
          <Bot size={18} /> Help
        </NavLink>
      </nav>
      <AskAI />
    </div>
  );
}
