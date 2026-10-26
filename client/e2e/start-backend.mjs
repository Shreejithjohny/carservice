// Starts a Django backend for the browser tests with a fresh, seeded throwaway database.
// Run by playwright.config.ts; never touches backend/db.sqlite3.
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const manage = resolve(here, "../../backend/manage.py");
const dataDir = join(here, ".data");
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const port = process.env.E2E_API_PORT || "8001";

mkdirSync(dataDir, { recursive: true });
const dbPath = join(dataDir, "e2e.sqlite3");
rmSync(dbPath, { force: true });

const env = { ...process.env, DEBUG: "True", OTP_BYPASS: "True", SQLITE_PATH: dbPath, IGNORE_DOTENV: "1" };

for (const args of [["migrate", "--noinput"], ["seed_vehicle_catalog"], ["seed_service_data"], ["seed_demo_accounts"]]) {
  const run = spawnSync(python, [manage, ...args], { env, stdio: "inherit" });
  if (run.status !== 0) {
    console.error(`manage.py ${args[0]} failed`);
    process.exit(run.status ?? 1);
  }
}

const server = spawn(python, [manage, "runserver", `127.0.0.1:${port}`, "--noreload"], { env, stdio: "inherit" });
const stop = () => server.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
server.on("exit", (code) => process.exit(code ?? 0));
