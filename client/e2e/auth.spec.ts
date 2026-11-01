import { expect, test } from "@playwright/test";
import { ACCOUNTS, signIn } from "./helpers";

test("customer signs in with email and password", async ({ page }) => {
  await signIn(page, "customer");
  await expect(page.getByRole("link", { name: "Book", exact: true })).toBeVisible();
});

test("a wrong password is refused", async ({ page }) => {
  await page.goto("/login/customer");
  await page.getByLabel(/email or mobile number/i).fill(ACCOUNTS.customer);
  await page.getByLabel("Password", { exact: true }).fill("not-the-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText(/incorrect|invalid|wrong/i).first()).toBeVisible();
  await expect(page).toHaveURL(/\/login\/customer$/);
});

test("each role has its own sign-in tab", async ({ page }) => {
  await page.goto("/login/driver");
  await expect(page.getByRole("heading", { name: "Driver sign in" })).toBeVisible();
  await page.getByRole("navigation", { name: "Sign in as" }).getByRole("link", { name: "Manager" }).click();
  await expect(page.getByRole("heading", { name: "Manager sign in" })).toBeVisible();
});

test("the demo button still appears when the page opens before the backend is ready", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/health-check/", async (route) => {
    calls += 1;
    // The first two checks fail as if the backend were still starting
    if (calls <= 2) await route.fulfill({ status: 502, body: "Bad Gateway" });
    else await route.continue();
  });
  await page.goto("/login/driver");
  await expect(page.getByRole("button", { name: /Try the demo driver account/ })).toBeVisible({ timeout: 15_000 });
  expect(calls).toBeGreaterThanOrEqual(3);
});
