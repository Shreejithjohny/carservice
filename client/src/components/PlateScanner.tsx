import { useState } from "react";
import { ScanLine, CheckCircle2, AlertTriangle } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";

interface PlateCheck {
  result: "MATCH" | "LIKELY_MATCH" | "MISMATCH" | "NO_TEXT";
  detected: string;
  expected: string;
  plate_verified: boolean;
}

/** Greyscale, stretch contrast and enlarge the photo: Tesseract reads plates far better that way. */
async function preprocess(file: File): Promise<HTMLCanvasElement> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(3, 1600 / bitmap.width);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const px = img.data;
  let min = 255;
  let max = 0;
  for (let i = 0; i < px.length; i += 4) {
    const g = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
    px[i] = g;
    min = Math.min(min, g);
    max = Math.max(max, g);
  }
  const range = Math.max(1, max - min);
  for (let i = 0; i < px.length; i += 4) {
    const v = ((px[i] - min) / range) * 255;
    px[i] = px[i + 1] = px[i + 2] = v;
  }
  ctx.putImageData(img, 0, 0);
  return canvas;
}

/**
 * Driver photographs the number plate; OCR runs in the browser (tesseract.js) and the backend checks
 * the text against the booking's registration. The OCR engine and language data (~7 MB) are served
 * from public/ocr/ and cached by the browser after the first scan.
 */
export function PlateScanner({ bookingId, verified, onVerified }: { bookingId: string | number; verified?: boolean; onVerified: () => void }) {
  const { push } = useToast();
  const [stage, setStage] = useState<"idle" | "reading" | "checking">("idle");
  const [progress, setProgress] = useState(0);
  const [check, setCheck] = useState<PlateCheck | null>(null);

  async function scan(file: File | undefined) {
    if (!file) return;
    setCheck(null);
    setStage("reading");
    setProgress(0);
    try {
      const { createWorker } = await import("tesseract.js");
      // Engine and language files are served by this app (copied to public/ocr/ at build time)
      const worker = await createWorker("eng", 1, {
        workerPath: "/ocr/worker.min.js",
        corePath: "/ocr",
        langPath: "/ocr",
        logger: (m: { status: string; progress: number }) => {
          if (m.status === "recognizing text") setProgress(Math.round(m.progress * 100));
        },
      });
      await worker.setParameters({ tessedit_char_whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- " });
      const { data } = await worker.recognize(await preprocess(file));
      await worker.terminate();

      setStage("checking");
      const res = await api<PlateCheck>(`/api/driver/pickups/${bookingId}/plate-check/`, {
        method: "POST",
        body: JSON.stringify({ ocr_text: data.text }),
      });
      setCheck(res);
      if (res.plate_verified) onVerified();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not read the plate. Please try again.", tone: "err" });
    } finally {
      setStage("idle");
    }
  }

  const ok = check && (check.result === "MATCH" || check.result === "LIKELY_MATCH");

  return (
    <div className="rounded-2xl border border-zinc-200 p-3 text-xs space-y-2 dark:border-zinc-700">
      <div className="flex items-center justify-between gap-2">
        <div>
          <span className="font-bold block">Number plate check</span>
          <span className="text-[11px] text-zinc-500">Photograph the plate to confirm this is the booked car.</span>
        </div>
        {verified ? (
          <span className="flex items-center gap-1 font-bold text-emerald-600">
            <CheckCircle2 size={14} /> Plate verified
          </span>
        ) : (
          <label className="flex cursor-pointer items-center gap-1 rounded-xl bg-zinc-800 px-3 py-1.5 font-bold text-white dark:bg-zinc-200 dark:text-zinc-900">
            <ScanLine size={14} />
            {stage === "reading" ? `Reading ${progress}%` : stage === "checking" ? "Checking..." : "Scan Plate"}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              disabled={stage !== "idle"}
              onChange={(e) => {
                void scan(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      {check && !verified && (
        <p className={`flex items-start gap-1 rounded-xl p-2 ${ok ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30" : "bg-amber-50 text-amber-700 dark:bg-amber-950/30"}`}>
          {ok ? <CheckCircle2 size={14} className="shrink-0" /> : <AlertTriangle size={14} className="shrink-0" />}
          {check.result === "NO_TEXT"
            ? "No text found. Move closer so the plate fills the photo, and avoid glare."
            : ok
              ? `Read "${check.detected}" — matches ${check.expected}.`
              : `Read "${check.detected || "?"}" but the booking is for ${check.expected}. Retake the photo, or check the car before taking it.`}
        </p>
      )}
    </div>
  );
}
