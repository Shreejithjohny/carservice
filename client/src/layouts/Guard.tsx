import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import type { Role } from "../types";

export function Guard({ roles }: { roles: (Role | string)[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-center text-zinc-500">Loading session…</div>;
  if (!user) return <Navigate to="/login" replace />;

  const userRoleLower = (user.role || "").toLowerCase();
  const allowedRolesLower = roles.map((r) => String(r).toLowerCase());

  const isAllowed =
    userRoleLower === "admin" ||
    allowedRolesLower.includes(userRoleLower) ||
    allowedRolesLower.includes(user.role);

  if (!isAllowed) return <Navigate to="/login" replace />;
  return <Outlet />;
}
