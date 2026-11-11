import { expect, test, type APIRequestContext } from "@playwright/test";
import { ACCOUNTS, PASSWORD, signIn, stubMapStyle } from "./helpers";

// One booking through all four roles, from the customer's booking to a paid invoice and a review:
// customer books -> admin confirms and assigns -> driver collects the car with the handover code ->
// mechanic services it and asks for an extra repair -> customer approves -> driver returns the car
// with the delivery code -> invoice -> customer pays and rates the service -> admin sees it paid.
// The driver's and mechanic's taps are made through the API (as their phones would); every screen a
// person reads the result on is checked in the browser.
test.describe.configure({ mode: "serial" });

const MECHANIC = "mechanic@smartdoorstep.com";
let bookingId = "";
let reference = "";
let headers: Record<string, Record<string, string>> = {};

async function tokenFor(request: APIRequestContext, identifier: string) {
  const login = await request.post("/api/auth/login/", { data: { identifier, password: PASSWORD } });
  expect(login.ok(), `sign in as ${identifier}`).toBeTruthy();
  return { Authorization: `Bearer ${(await login.json()).access}` };
}

test.beforeEach(async ({ page }) => {
  await stubMapStyle(page);
});

test("customer books, admin confirms and assigns the driver and mechanic", async ({ page, request }) => {
  headers = {
    admin: await tokenFor(request, ACCOUNTS.admin),
    driver: await tokenFor(request, ACCOUNTS.driver),
    mechanic: await tokenFor(request, MECHANIC),
    customer: await tokenFor(request, ACCOUNTS.customer),
  };

  await signIn(page, "customer");
  await page.goto("/app/book");
  await page.locator('button:has-text("places left")').nth(1).click();
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/bookings/") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Confirm & Schedule/ }).click(),
  ]);
  expect(created.status()).toBe(201);
  const booking = await created.json();
  bookingId = String(booking.id);
  reference = booking.booking_reference;

  // The admin assigns the demo driver and mechanic, so the next steps know who has the job
  const staff = await (await request.get("/api/service-center/employees/", { headers: headers.admin })).json();
  const driver = staff.drivers.find((d: { email: string }) => d.email === ACCOUNTS.driver);
  const mechanic = staff.mechanics.find((m: { email: string }) => m.email === MECHANIC);
  const confirmed = await request.patch(`/api/service-center/bookings/${bookingId}/`, {
    headers: headers.admin,
    data: { status: "Confirmed", assigned_driver_id: driver.id, assigned_mechanic_id: mechanic.id },
  });
  expect(confirmed.status()).toBe(200);

  await signIn(page, "admin");
  await page.goto("/admin/bookings");
  const card = page.getByRole("article", { name: `Booking ${reference}` });
  await expect(card.getByText("Confirmed", { exact: true })).toBeVisible();
  await expect(card.getByText(/Valet: (?!Unassigned)/)).toBeVisible();
});

test("driver collects the car with the code shown to the customer", async ({ page, request }) => {
  expect((await request.post(`/api/driver/pickups/${bookingId}/status/`, { headers: headers.driver, data: { status: "En Route for Pickup" } })).status()).toBe(200);
  expect((await request.post(`/api/driver/pickups/${bookingId}/handover-otp/request/`, { headers: headers.driver })).status()).toBe(200);

  // The customer reads the 6-digit handover code on the Track page
  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await expect(page.getByRole("heading", { name: reference })).toBeVisible();
  const code = (await page.locator("p.font-mono.text-4xl").first().textContent())?.trim() ?? "";
  expect(code).toMatch(/^\d{6}$/);

  // A wrong code is refused; the right one hands the car over
  const wrong = code === "000001" ? "000002" : "000001";
  expect((await request.post(`/api/driver/pickups/${bookingId}/handover-otp/verify/`, { headers: headers.driver, data: { otp_code: wrong } })).status()).toBe(400);
  expect((await request.post(`/api/driver/pickups/${bookingId}/handover-otp/verify/`, { headers: headers.driver, data: { otp_code: code } })).status()).toBe(200);

  await page.reload();
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await expect(page.locator("p.font-mono.text-4xl")).toHaveCount(0); // the used code is no longer shown
});

test("mechanic asks for an extra repair and the customer approves it", async ({ page, request }) => {
  expect((await request.patch(`/api/mechanic/jobs/${bookingId}/status/`, { headers: headers.mechanic, data: { status: "In Service" } })).status()).toBe(200);
  const repair = await request.post("/api/repair-requests/", {
    headers: headers.mechanic,
    data: { booking: Number(bookingId), issue_title: "Front brake pads", description: "Worn below 2 mm", additional_cost: 1800, estimated_extra_hours: 1 },
  });
  expect(repair.status()).toBe(201);

  await signIn(page, "customer");
  await page.goto("/app/approvals");
  await expect(page.getByText("Front brake pads").first()).toBeVisible();
  const [approved] = await Promise.all([
    page.waitForResponse((r) => /\/api\/repair-requests\/\d+\/approve\/$/.test(r.url())),
    page.getByRole("button", { name: "Approve Repair" }).first().click(),
  ]);
  expect(approved.status()).toBe(200);
  await expect(page.getByText("Additional repair approved successfully!")).toBeVisible();
});

test("driver returns the car with the delivery code, which creates the invoice", async ({ page, request }) => {
  expect((await request.patch(`/api/mechanic/jobs/${bookingId}/status/`, { headers: headers.mechanic, data: { status: "Ready for Delivery" } })).status()).toBe(200);
  expect((await request.post(`/api/driver/pickups/${bookingId}/status/`, { headers: headers.driver, data: { status: "Out for Delivery" } })).status()).toBe(200);
  expect((await request.post(`/api/driver/pickups/${bookingId}/delivery-otp/request/`, { headers: headers.driver })).status()).toBe(200);

  await signIn(page, "customer");
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  const code = (await page.locator("p.font-mono.text-4xl").first().textContent())?.trim() ?? "";
  expect(code).toMatch(/^\d{6}$/);
  expect((await request.post(`/api/driver/pickups/${bookingId}/delivery-otp/verify/`, { headers: headers.driver, data: { otp_code: code } })).status()).toBe(200);

  const tracking = await (await request.get(`/api/bookings/${bookingId}/tracking/`, { headers: headers.customer })).json();
  expect(tracking.booking.status).toBe("Completed");
});

test("customer pays the invoice and rates the service; the admin sees it paid", async ({ page, request }) => {
  const invoices = await (await request.get("/api/invoices/", { headers: headers.customer })).json();
  const invoice = invoices.find((i: { booking: number }) => String(i.booking) === bookingId);
  expect(invoice, "an invoice was created when the car was delivered").toBeTruthy();
  // Package + approved repair (1,800) + one hour of labour (400), plus 18% GST
  const base = Number(invoice.subtotal);
  expect(Number(invoice.additional_repairs_total)).toBe(1800);
  expect(Number(invoice.labor_total)).toBe(400);
  expect(Number(invoice.grand_total)).toBeCloseTo((base + 1800 + 400 - Number(invoice.discount)) * 1.18, 1);

  await signIn(page, "customer");
  await page.goto("/app/invoices");
  // The "Pay now" button on this invoice's own card
  await page
    .locator("div")
    .filter({ has: page.getByText(invoice.invoice_number, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Pay now" }) })
    .last()
    .getByRole("button", { name: "Pay now" })
    .click();
  await page.getByLabel("UPI ID").fill("meera@okbank");
  const [paid] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/invoices/${invoice.id}/pay/`)),
    page.getByRole("button", { name: /^Pay ₹/ }).click(),
  ]);
  expect(paid.status()).toBe(200);
  await expect(page.getByText(/Payment successful/).first()).toBeVisible();

  // Rating appears on the Track page once the booking is completed
  await page.goto("/app/track");
  await page.getByLabel("Select Booking:").selectOption(bookingId);
  await page.getByRole("radiogroup", { name: "Service center" }).getByRole("radio", { name: "5 stars" }).click();
  await page.getByRole("radiogroup", { name: "Pickup driver" }).getByRole("radio", { name: "4 stars" }).click();
  await page.getByRole("button", { name: "Submit review" }).click();
  await expect(page.getByText("Thanks for your feedback!")).toBeVisible();

  // The admin's invoice list shows it paid, and admins were told about the payment
  const adminInvoices = await (await request.get("/api/invoices/", { headers: headers.admin })).json();
  expect(adminInvoices.find((i: { id: number }) => i.id === invoice.id).payment_status).toBe("PAID");
  const alerts = await (await request.get("/api/notifications/", { headers: headers.admin })).json();
  expect(alerts.some((n: { title: string; message: string }) => n.title === "Invoice paid" && n.message.includes(invoice.invoice_number))).toBeTruthy();
});
