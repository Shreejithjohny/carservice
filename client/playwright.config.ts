import { randomBytes } from "node:crypto";
import { defineConfig, devices } from "@playwright/test";

// The browser tests start their own backend (fresh seeded database) and frontend on separate
// ports, so they never touch the dev servers or backend/db.sqlite3.
const API_PORT = process.env.E2E_API_PORT || "8001";
const WEB_PORT = process.env.E2E_WEB_PORT || "5174";

// Password for the seeded demo accounts: random per run, so none is written in the code.
// Set here once; the test workers inherit it through the environment.
process.env.E2E_PASSWORD ||= `E2e-${randomBytes(9).toString("base64url")}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // the tests share one database and build on each other's bookings
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    geolocation: { latitude: 12.9698, longitude: 77.7499 },
    permissions: ["geolocation"],
  },
  projects: [
    {
      name: "chromium",
      // SwiftShader gives headless Chromium the WebGL the maps need, also on CI machines without a GPU
      use: { ...devices["Desktop Chrome"], launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] } },
    },
  ],
  webServer: [
    {
      command: "node e2e/start-backend.mjs",
      url: `http://127.0.0.1:${API_PORT}/api/health-check/`,
      env: { E2E_API_PORT: API_PORT, DEMO_ACCOUNT_PASSWORD: process.env.E2E_PASSWORD },
      timeout: 180_000,
      reuseExistingServer: false,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      // Listen on 127.0.0.1 explicitly: on machines where "localhost" means IPv6 (::1), such as
      // GitHub's Ubuntu runners, Vite would otherwise not answer at the address checked below
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { VITE_API_PROXY: `http://127.0.0.1:${API_PORT}`, VITE_GOOGLE_MAPS_API_KEY: "" },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
