// Copies the tesseract.js worker, WebAssembly core and English language data into public/ocr/,
// so number plate OCR works without reaching the jsdelivr CDN (e.g. on a college network).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const out = join(dirname(new URL(import.meta.url).pathname), "..", "public", "ocr");
mkdirSync(out, { recursive: true });

const pkgDir = (name) => dirname(require.resolve(`${name}/package.json`));
const files = [
  [join(pkgDir("tesseract.js"), "dist", "worker.min.js"), "worker.min.js"],
  // OEM 1 (LSTM only) picks one of these depending on the browser's WebAssembly SIMD support
  ...["tesseract-core-lstm.wasm.js", "tesseract-core-simd-lstm.wasm.js", "tesseract-core-relaxedsimd-lstm.wasm.js"].map(
    (f) => [join(pkgDir("tesseract.js-core"), f), f]
  ),
  [join(pkgDir("@tesseract.js-data/eng"), "4.0.0_best_int", "eng.traineddata.gz"), "eng.traineddata.gz"],
];
for (const [from, name] of files) copyFileSync(from, join(out, name));
console.log(`Copied ${files.length} OCR files to public/ocr/`);
