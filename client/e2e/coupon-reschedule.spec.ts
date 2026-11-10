import { expect, test } from "@playwright/test";
import { signIn, stubMapStyle } from "./helpers";

// The customer confirms their number, uses a coupon, then moves the pickup to another slot.
test.describe.configure({ mode: "serial" });

let bookingId = "";
let reference = "";

test.beforeEach(async ({ page }) => {
  await stubMapStyle(page);
});

test("booking asks for the driver's contact number and takes a coupon", async ({ page }) => {
  await signIn(page, "customer");
  await page.goto("/app/book");

  // The number from the profile is filled in for the customer to check; an unusable one is refused
  const phone = page.getByLabel("Mobile number for the driver");
  await expect(phone).not.toHaveValue("");
  const profileNumber = await phone.inputValue();
  await phone.fill("123");
  await page.locator('button:has-text("places left")').first().click();
  await page.getByRole("button", { name: /Confirm & Schedule/ }).click();
  await expect(page.getByText("Enter the 10-digit mobile number our driver should call")).toBeVisible();
  await phone.fill("98450 12345");

  // A wrong code is explained; the demo coupon takes 10% off
  await page.getByLabel("Coupon code (optional)").fill("nosuchcode");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("This coupon code is not valid.")).toBeVisible();
  await page.getByLabel("Coupon code (optional)").fill("welcome10");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText(/WELCOME10: ₹[\d,]+(\.\d{2})? off the package price/)).toBeVisible();

  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/bookings/") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Confirm & Schedule/ }).click(),
  ]);
  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.contact_phone).toBe("+919845012345");
  expect(body.customer_phone).toBe("+919845012345");
  expect(body.coupon_code).toBe("WELCOME10");
  expect(Number(body.coupon_discount)).toBeCloseTo(Math.min(300, Number(body.estimated_cost) * 0.1), 2);
  bookingId = String(body.id);
  reference = body.booking_reference;
  await expect(page.getByText("+919845012345")).toBeVisible();
  expect(profileNumber).not.toBe("");
});

test("the customer reschedules the pickup to another slot", async ({ page }) => {
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await expect(page.getByRole("heading", { name: reference })).toBeVisible();

  await page.getByRole("button", { name: "Reschedule pickup" }).click();
  const dialog = page.getByRole("dialog", { name: "Reschedule pickup" });
  // The slot the booking already has can't be picked again
  await expect(dialog.getByRole("button", { name: /Current slot/ })).toBeDisabled();
  const target = dialog.locator('button:has-text("places left")').last();
  const label = (await target.locator("span").first().textContent()) ?? "";
  await target.click();
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/bookings/${bookingId}/`) && r.request().method() === "PATCH"),
    dialog.getByRole("button", { name: "Move pickup to this slot" }).click(),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.getByText(new RegExp(`Pickup moved to .*${label.slice(0, 8)}`))).toBeVisible();
  await expect(dialog).toBeHidden();

  // The customer was told inside the app as well
  await page.goto("/app/notifications");
  await expect(page.getByText("Pickup rescheduled").first()).toBeVisible();
});
