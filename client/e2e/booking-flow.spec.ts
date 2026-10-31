import { expect, test } from "@playwright/test";
import { ACCOUNTS, PASSWORD, signIn, stubMapStyle } from "./helpers";

// One story across three screens: the customer books, the manager confirms (and the app picks the
// driver), then the customer tracks it. Later steps use the booking made in the first one; in serial
// mode Playwright skips the remaining steps when one fails.
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
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await expect(page.getByRole("heading", { name: reference })).toBeVisible();
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  // Pickup pin and workshop marker
  await expect(page.locator(".maplibregl-marker")).toHaveCount(2);
  await expect(page.getByText("Waiting for the driver's GPS")).toBeVisible();
});

test("the driver's GPS shows a car, the road route and an ETA", async ({ page, request }) => {
  // The driver's phone shares its position (as the driver dashboard does every 10 seconds)
  const login = await request.post("/api/auth/login/", { data: { identifier: ACCOUNTS.driver, password: PASSWORD } });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).access}` };
  // Driving north-west towards the Whitefield pickup point
  for (const [latitude, longitude] of [[12.9600, 77.7300], [12.9640, 77.7390]]) {
    const sent = await request.post(`/api/driver/pickups/${bookingId}/location/`, { headers, data: { latitude, longitude } });
    expect(sent.status()).toBe(201);
  }

  // Road route from the routing service (OSRM via our backend); answered here so the test is offline
  await page.route("**/api/location/route/**", (route) =>
    route.fulfill({
      json: {
        coordinates: [[77.739, 12.964], [77.744, 12.966], [77.7499, 12.9698]],
        distance_km: 1.4,
        duration_min: 6,
      },
    })
  );
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);

  await expect(page.locator(".map-car")).toBeVisible();
  const eta = page.getByRole("region", { name: "Estimated arrival" });
  await expect(eta).toContainText("Driver arriving in");
  await expect(eta).toContainText("6 min");
  await expect(eta).toContainText("1.4 km by road");
  await expect(page.getByText(/Live · driver GPS/)).toBeVisible();
});

test("without a road route the ETA falls back to a labelled straight-line estimate", async ({ page }) => {
  await page.route("**/api/location/route/**", (route) => route.fulfill({ status: 502, json: { error: "Road routes are unavailable right now." } }));
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  const eta = page.getByRole("region", { name: "Estimated arrival" });
  await expect(eta).toContainText("straight-line estimate");
});
