import { expect, test } from "@playwright/test";
import { signIn, stubMapStyle } from "./helpers";

// One story across three screens: the customer books, the manager confirms (and the app picks the
// driver), then the customer tracks it. Later steps use the booking made in the first one.
test.describe.configure({ mode: "serial" });

let reference = "";
let bookingId = "";

test.beforeEach(async ({ page }) => {
  await stubMapStyle(page);
});

test("customer books a pickup by placing the pin on the map", async ({ page }) => {
  await signIn(page, "customer");
  await page.goto("/app/book");
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();

  await page.getByRole("button", { name: "Whitefield Main Road" }).click();
  await expect(page.getByLabel("Full pickup address (add flat / house number)")).toHaveValue("Whitefield Main Road");
  await page.getByLabel("Full pickup address (add flat / house number)").fill("Flat 4B, Whitefield Main Road, Bengaluru");

  await page.locator('button:has-text("places left")').first().click();
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/bookings/") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Confirm & Schedule/ }).click(),
  ]);
  expect(response.status()).toBe(201);
  const sent = response.request().postDataJSON();
  expect(sent.pickup_address).toBe("Flat 4B, Whitefield Main Road, Bengaluru");
  expect(sent.pickup_latitude).toBeCloseTo(12.9698, 3);
  expect(sent.pickup_longitude).toBeCloseTo(77.7499, 3);

  const body = await response.json();
  reference = body.booking_reference;
  bookingId = String(body.id);
  expect(reference).toMatch(/^SDV-/);
  await expect(page.getByText(reference)).toBeVisible();
});

test("manager confirms it and a driver is assigned automatically", async ({ page }) => {
  test.skip(!reference, "needs the booking from the previous test");
  await signIn(page, "manager");
  await page.goto("/service-center/bookings");
  const card = page.getByRole("article", { name: `Booking ${reference}` });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Confirm", exact: true }).click();

  await expect(page.getByText(/Confirmed\. Auto-assigned driver/)).toBeVisible();
  await expect(card.getByText("Confirmed", { exact: true })).toBeVisible();
  await expect(card.getByText(/Valet: (?!Unassigned)/)).toBeVisible();
});

test("customer sees the booking on the tracking map", async ({ page }) => {
  test.skip(!reference, "needs the booking from the previous test");
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await expect(page.getByRole("heading", { name: reference })).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  // Pickup pin and workshop marker
  await expect(page.locator(".maplibregl-marker")).toHaveCount(2);
  await expect(page.getByText("Waiting for the driver's GPS")).toBeVisible();
});
