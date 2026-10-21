import { seedIfEmpty } from "./seed.js";

seedIfEmpty().then(() => {
  console.log("Seed complete");
});
