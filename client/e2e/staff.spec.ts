import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("an admin adds a driver, who can then sign in on the Driver tab", async ({ page }) => {
  const email = `driver-${Date.now()}@example.com`;
  await signIn(page, "admin");
  await page.getByRole("link", { name: "Staff" }).click();
  await expect(page).toHaveURL(/\/admin\/staff$/);

  const form = page.getByRole("form", { name: "Add a driver or mechanic" });
  await form.getByLabel("Full name").fill("Ravi Kumar");
  await form.getByLabel("Work email (used to sign in)").fill(email);
  await form.getByRole("button", { name: "Generate" }).click();
  const password = await form.getByLabel("First password").inputValue();
  expect(password).toMatch(/^[A-Za-z][A-Za-z2-9]{10}\d$/);
  await form.getByLabel("Service center").selectOption({ index: 1 });
  await form.getByRole("button", { name: "Add driver" }).click();

  const created = page.getByRole("region", { name: "New account" });
  await expect(created).toContainText("Ravi Kumar can now sign in as a driver");
  await expect(created).toContainText(`Password: ${password}`);
  const member = page.getByRole("listitem", { name: "Ravi Kumar" });
  await expect(member.getByRole("button", { name: "On duty" })).toBeVisible();

  // Off duty and back
  await member.getByRole("button", { name: "On duty" }).click();
  await expect(member.getByRole("button", { name: "Off duty" })).toBeVisible();
  await member.getByRole("button", { name: "Off duty" }).click();
  await expect(member.getByRole("button", { name: "On duty" })).toBeVisible();

  // The new driver signs in with those details
  await page.evaluate(() => localStorage.clear());
  await page.goto("/login/driver");
  await page.getByLabel(/email or mobile number/i).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/driver$/);
});
