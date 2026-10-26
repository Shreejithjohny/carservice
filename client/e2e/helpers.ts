import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.E2E_PASSWORD ?? "";

export const ACCOUNTS = {
  customer: "customer@smartdoorstep.com",
  manager: "manager@smartdoorstep.com",
  driver: "driver@smartdoorstep.com",
} as const;

const HOME = { customer: "/app", manager: "/service-center", driver: "/driver" } as const;

/**
 * Serve a tiny stand-in for the OpenFreeMap style, so the tests don't depend on an outside map
 * server. The map engine, markers and our code all still run for real.
 */
export async function stubMapStyle(page: Page) {
  await page.route("**/styles/liberty", (route) =>
    route.fulfill({ json: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#eef0f3" } }] } })
  );
}

/** Sign in through the real sign-in page with email + password. */
export async function signIn(page: Page, role: keyof typeof ACCOUNTS) {
  await page.goto(`/login/${role}`);
  await page.getByLabel(/email or mobile number/i).fill(ACCOUNTS[role]);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${HOME[role]}$`));
}
