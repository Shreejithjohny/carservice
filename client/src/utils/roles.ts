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

export function homePathForRole(role: string) {
  return HOME_PATHS[role.toLowerCase() as Role] ?? "/app";
}
