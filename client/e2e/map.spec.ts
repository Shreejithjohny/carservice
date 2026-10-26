import { expect, test } from "@playwright/test";
import { signIn, stubMapStyle } from "./helpers";

test.beforeEach(async ({ page }) => {
  await stubMapStyle(page);
  // Address lookups normally go to OpenStreetMap through our backend; answer them here instead
  await page.route("**/api/location/reverse/**", (route) => route.fulfill({ json: { address: "17th Main Road, HSR Layout, Bengaluru" } }));
  await page.route("**/api/location/search/**", (route) =>
    route.fulfill({ json: { results: [{ label: "Koramangala 5th Block, Bengaluru, Karnataka", latitude: 12.9345, longitude: 77.6186 }] } })
  );
  await signIn(page, "customer");
  await page.goto("/app/book");
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
});

const addressBox = (page: import("@playwright/test").Page) => page.getByLabel("Full pickup address (add flat / house number)");

test("dragging the map under the pin looks up the address", async ({ page }) => {
  const box = (await page.locator(".maplibregl-canvas").boundingBox())!;
  const [x, y] = [box.x + box.width / 2, box.y + box.height / 2];
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(x - i * 12, y - i * 6);
  await expect(page.locator(".map-center-pin.lifted")).toHaveCount(1); // pin lifts while dragging
  await page.mouse.up();

  await expect(addressBox(page)).toHaveValue("17th Main Road, HSR Layout, Bengaluru");
  await expect(page.locator(".map-center-pin.lifted")).toHaveCount(0);
});

test("a search result moves the map and fills the address", async ({ page }) => {
  await page.getByLabel("Search for a place").fill("Koramangala");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("button", { name: "Koramangala 5th Block, Bengaluru, Karnataka" }).click();
  await expect(addressBox(page)).toHaveValue("Koramangala 5th Block, Bengaluru, Karnataka");
  // Moving the map for a search result must not replace the chosen address with a lookup
  await page.waitForTimeout(1500);
  await expect(addressBox(page)).toHaveValue("Koramangala 5th Block, Bengaluru, Karnataka");
});

test("'Use my location' moves the pin to the phone's GPS position", async ({ page }) => {
  await page.getByRole("button", { name: /Use my location/ }).click();
  await expect(addressBox(page)).toHaveValue("17th Main Road, HSR Layout, Bengaluru");
  // Straight-line distance card is shown for the selected workshop
  await expect(page.getByText(/km/).first()).toBeVisible();
});
