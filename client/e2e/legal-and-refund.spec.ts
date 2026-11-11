import { expect, test } from "@playwright/test";
import { ACCOUNTS, PASSWORD, signIn } from "./helpers";

test("the legal pages are public and linked from the landing and sign-in pages", async ({ page }) => {
  await page.goto("/");
  const footer = page.getByRole("contentinfo");
  await expect(footer.getByRole("link")).toHaveText(["Privacy", "Terms", "Refunds & cancellation", "Contact"]);

  await footer.getByRole("link", { name: "Privacy" }).click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { name: "Privacy Policy", level: 1 })).toBeVisible();
  await expect(page.getByText(/never reach us/)).toBeVisible(); // card details stay with the payment provider

  await page.getByRole("navigation", { name: "Policies" }).getByRole("link", { name: "Refunds & cancellation" }).click();
  await expect(page.getByRole("heading", { name: "Refunds & Cancellation", level: 1 })).toBeVisible();
  await expect(page.getByText(/original payment method/)).toBeVisible();

  await page.goto("/terms");
  await expect(page.getByRole("heading", { name: "Terms of Service", level: 1 })).toBeVisible();
  await page.goto("/contact");
  await expect(page.getByRole("heading", { name: "Contact Us", level: 1 })).toBeVisible();
  // Business details come from the server's BUSINESS_* settings; unset ones are easy to spot
  await expect(page.getByText("[not set]").first()).toBeVisible();

  await page.goto("/login/customer");
  await expect(page.getByRole("contentinfo").getByRole("link", { name: "Terms" })).toBeVisible();
});

// Uses the invoice paid in full-lifecycle.spec.ts (the specs run in file-name order on one database)
test("an admin refunds a payment from the invoice page and the customer is told", async ({ page, request }) => {
  const tokenFor = async (identifier: string) => {
    const login = await request.post("/api/auth/login/", { data: { identifier, password: PASSWORD } });
    return { Authorization: `Bearer ${(await login.json()).access}` };
  };
  const admin = await tokenFor(ACCOUNTS.admin);
  const invoices: { id: number; invoice_number: string; payment_status: string; grand_total: string }[] =
    await (await request.get("/api/invoices/", { headers: admin })).json();
  const invoice = invoices.find((i) => i.payment_status === "PAID");
  expect(invoice, "a paid invoice from the lifecycle test").toBeTruthy();

  await signIn(page, "admin");
  await page.goto("/admin/invoices");
  await page.getByText(invoice!.invoice_number, { exact: true }).first().click();
  const refundButton = page.getByRole("button", { name: /^Refund ₹/ });
  await expect(refundButton).toBeVisible();

  // Cancelling the question changes nothing
  page.once("dialog", (dialog) => void dialog.dismiss());
  await refundButton.click();
  await expect(refundButton).toBeVisible();

  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("cannot be undone");
    void dialog.accept("Customer was charged for work not done");
  });
  const [response] = await Promise.all([
    page.waitForResponse((r) => /\/api\/payments\/\d+\/refund\/$/.test(r.url())),
    refundButton.click(),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.getByText("Refund issued. The customer has been notified.")).toBeVisible();
  await expect(page.getByText(/Refunded on .* Customer was charged for work not done/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Refund ₹/ })).toHaveCount(0);

  // The invoice is now Refunded and cancelled, so the customer sees no Pay button and got an alert
  const customer = await tokenFor(ACCOUNTS.customer);
  const after = (await (await request.get("/api/invoices/", { headers: customer })).json()).find((i: { id: number }) => i.id === invoice!.id);
  expect([after.payment_status, after.invoice_status]).toEqual(["REFUNDED", "CANCELLED"]);
  const alerts = await (await request.get("/api/notifications/", { headers: customer })).json();
  expect(alerts.some((n: { title: string }) => n.title === "Refund issued")).toBeTruthy();
});
