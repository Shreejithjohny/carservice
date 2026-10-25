import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import type { Role } from "../types";
import { signInPathForRole } from "../utils/roles";

// Admins can open every section; everyone else only the sections listed for their role.
export function Guard({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-center text-zinc-500">Loading session…</div>;
  // Send people to the sign-in tab of the section they were trying to open
  if (!user) return <Navigate to={signInPathForRole(roles[0])} replace />;

  const role = user.role.toLowerCase() as Role;
  if (role !== "admin" && !roles.includes(role)) return <Navigate to={signInPathForRole(roles[0])} replace />;
  return <Outlet />;
}
