import { expect, test } from "@playwright/test";
import { ACCOUNTS, PASSWORD, signIn, stubMapStyle } from "./helpers";

// One story across three screens: the customer books, the admin confirms (and the app picks the
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

test("admin confirms it and a driver is assigned automatically", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/admin/bookings");
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

test("the driver shares live GPS from the dashboard, and it stays on after a reload", async ({ page }) => {
  await signIn(page, "driver");
  const job = page.getByRole("article", { name: `Job ${reference}` });
  const [sent] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/driver/pickups/${bookingId}/location/`) && r.request().method() === "POST"),
    job.getByRole("button", { name: "Enable GPS" }).click(),
  ]);
  expect(sent.status()).toBe(201);
  // The test browser is placed at the Whitefield pickup point (playwright.config.ts)
  expect(sent.request().postDataJSON()).toEqual({ latitude: 12.9698, longitude: 77.7499 });
  await expect(job.getByText(/Customer can see you live/)).toBeVisible();

  await page.reload();
  await expect(job.getByRole("button", { name: "Stop sharing" })).toBeVisible();
  await job.getByRole("button", { name: "Stop sharing" }).click();
  await expect(job.getByText(/Not sharing/)).toBeVisible();
});

test("a blocked location permission is reported instead of pretending to track", async ({ page, context }) => {
  await context.clearPermissions();
  await signIn(page, "driver");
  const job = page.getByRole("article", { name: `Job ${reference}` });
  await job.getByRole("button", { name: "Enable GPS" }).click();
  await expect(job.getByText(/Location permission is blocked/)).toBeVisible();
  await job.getByRole("button", { name: "Stop sharing" }).click();
});

test("demo mode can simulate the drive along the road route", async ({ page, request }) => {
  await page.route("**/api/location/route/**", (route) =>
    route.fulfill({ json: { coordinates: [[77.6408, 12.9784], [77.7, 12.975], [77.7499, 12.9698]], distance_km: 12.1, duration_min: 30 } })
  );
  await signIn(page, "driver");
  const job = page.getByRole("article", { name: `Job ${reference}` });
  await job.getByRole("button", { name: "Simulate drive" }).click();
  await expect(job.getByText(/Driving… position 3 of/)).toBeVisible({ timeout: 15_000 });
  // GPS sharing is paused while the simulation runs
  await expect(job.getByRole("button", { name: "Enable GPS" })).toBeDisabled();
  await job.getByRole("button", { name: "Stop simulation" }).click();

  // The customer's tracking data now holds the simulated positions, starting at the workshop
  const login = await request.post("/api/auth/login/", { data: { identifier: ACCOUNTS.customer, password: PASSWORD } });
  const headers = { Authorization: `Bearer ${(await login.json()).access}` };
  const tracking = await (await request.get(`/api/bookings/${bookingId}/tracking/`, { headers })).json();
  const simulated = tracking.driver_route.filter((p: { longitude: number }) => p.longitude < 77.72);
  expect(simulated.length).toBeGreaterThanOrEqual(3);
  expect(simulated[0].latitude).toBeCloseTo(12.9784, 3);
  expect(simulated[0].longitude).toBeCloseTo(77.6408, 3);
});
