import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// A real 64x40 JPEG (blue) made in the browser, so the test needs no image files
async function makeJpeg(page: import("@playwright/test").Page): Promise<Buffer> {
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 40;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#1d4ed8";
    ctx.fillRect(0, 0, 64, 40);
    return canvas.toDataURL("image/jpeg").split(",")[1];
  });
  return Buffer.from(base64, "base64");
}

test("a customer replaces the initials with a photo, then removes it", async ({ page }) => {
  await signIn(page, "customer");
  const avatarButton = page.getByRole("button", { name: "Profile photo" });
  // No photo yet: initials, and no request to an outside avatar service
  await expect(avatarButton).toContainText(/^[A-Z]{2}$/);
  await expect(avatarButton.locator("img")).toHaveCount(0);

  await avatarButton.click();
  const dialog = page.getByRole("dialog", { name: "Profile photo" });
  await dialog.getByLabel("Choose a profile photo").setInputFiles({ name: "me.jpg", mimeType: "image/jpeg", buffer: await makeJpeg(page) });
  await expect(page.getByText("Profile photo updated")).toBeVisible();

  const img = avatarButton.locator("img");
  await expect(img).toHaveAttribute("src", /^\/api\/avatars\/[0-9a-f]{32}\.jpg$/);
  // The photo really loads, at the stored 256x256 size
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBe(256);

  await dialog.getByRole("button", { name: "Remove photo" }).click();
  await expect(page.getByText("Profile photo removed")).toBeVisible();
  await expect(avatarButton.locator("img")).toHaveCount(0);
  await expect(avatarButton).toContainText(/^[A-Z]{2}$/);
});

test("a file that isn't a photo is refused with a clear message", async ({ page }) => {
  await signIn(page, "customer");
  await page.getByRole("button", { name: "Profile photo" }).click();
  const dialog = page.getByRole("dialog", { name: "Profile photo" });
  await dialog.getByLabel("Choose a profile photo").setInputFiles({ name: "notes.jpg", mimeType: "image/jpeg", buffer: Buffer.from("not a photo") });
  await expect(page.getByText(/isn't a photo we can read/)).toBeVisible();
});
