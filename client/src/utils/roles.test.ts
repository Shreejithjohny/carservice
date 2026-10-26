import { describe, expect, it } from "vitest";
import { homePathForRole, signInPathForRole } from "./roles";

describe("signInPathForRole", () => {
  it("maps each role to its own sign-in tab", () => {
    expect(signInPathForRole("customer")).toBe("/login/customer");
    expect(signInPathForRole("service_center_manager")).toBe("/login/manager");
    expect(signInPathForRole("driver")).toBe("/login/driver");
  });

  it("accepts the backend's upper-case roles", () => {
    expect(signInPathForRole("MECHANIC")).toBe("/login/mechanic");
  });

  it("falls back to the customer tab for unknown roles", () => {
    expect(signInPathForRole("pilot")).toBe("/login/customer");
  });
});

describe("homePathForRole", () => {
  it("sends each role to its own area", () => {
    expect(homePathForRole("customer")).toBe("/app");
    expect(homePathForRole("SERVICE_CENTER_MANAGER")).toBe("/service-center");
    expect(homePathForRole("admin")).toBe("/admin");
    expect(homePathForRole("unknown")).toBe("/app");
  });
});
