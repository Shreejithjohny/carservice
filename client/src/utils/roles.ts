import type { Role } from "../types";

export const ROLE_LABELS: Record<Role, string> = {
  customer: "Customer",
  service_center_manager: "Manager",
  driver: "Driver",
  mechanic: "Mechanic",
  admin: "Admin",
};

const HOME_PATHS: Record<Role, string> = {
  customer: "/app",
  service_center_manager: "/service-center",
  driver: "/driver",
  mechanic: "/mechanic",
  admin: "/admin",
};

// URL part of each role's sign-in tab: /login/customer, /login/driver, ...
export const SIGN_IN_SLUGS: Record<Role, string> = {
  customer: "customer",
  driver: "driver",
  mechanic: "mechanic",
  service_center_manager: "manager",
  admin: "admin",
};

/** The sign-in URL for a role, e.g. "service_center_manager" -> "/login/manager". */
export function signInPathForRole(role: string) {
  return `/login/${SIGN_IN_SLUGS[role.toLowerCase() as Role] ?? "customer"}`;
}

export function homePathForRole(role: string) {
  return HOME_PATHS[role.toLowerCase() as Role] ?? "/app";
}
