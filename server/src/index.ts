import express from "express";
import cors from "cors";
import { join } from "node:path";
import { connectMongo } from "./lib/db.js";
import { router } from "./routes/index.js";
import { seedIfEmpty } from "./seed.js";
import "./models/register.js";

const app = express();
const PORT = Number(process.env.PORT || 4000);

app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: "8mb" }));
app.use("/uploads", express.static(join(process.cwd(), "uploads")));
app.use("/api", router);

app.get("/api/healthz", (_req, res) => res.json({ ok: true }));

async function main() {
  await connectMongo();
  await seedIfEmpty();
  app.listen(PORT, () => {
    console.log(`API http://localhost:${PORT}`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
