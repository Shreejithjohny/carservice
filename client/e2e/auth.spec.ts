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
