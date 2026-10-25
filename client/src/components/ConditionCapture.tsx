import { useState } from "react";
import { Camera, CheckCircle2, Gauge } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { ConditionReport } from "../types";

export const CONDITION_ANGLES = [
  { value: "FRONT", label: "Front" },
  { value: "REAR", label: "Rear" },
  { value: "LEFT", label: "Left side" },
  { value: "RIGHT", label: "Right side" },
  { value: "INTERIOR", label: "Interior" },
  { value: "ODOMETER", label: "Odometer" },
  { value: "OTHER", label: "Close-up / damage" },
];

/** Driver panel: photograph the car from each side and record the odometer, at pickup or at delivery. */
export function ConditionCapture({ bookingId, stage }: { bookingId: string | number; stage: "PICKUP" | "DELIVERY" }) {
  const { data: report, reload } = useApi<ConditionReport>(`/api/bookings/${bookingId}/condition-report/`);
  const { push } = useToast();
  const [uploading, setUploading] = useState<string | null>(null);
  const [odometer, setOdometer] = useState("");

  const photos = stage === "PICKUP" ? report?.pickup_photos : report?.delivery_photos;
  const done = new Set((photos ?? []).map((p) => p.angle));
  const savedReading = stage === "PICKUP" ? report?.pickup_odometer_km : report?.delivery_odometer_km;

  async function upload(angle: string, file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("angle", angle);
    form.append("file", file);
    setUploading(angle);
    try {
      await api(`/api/driver/pickups/${bookingId}/condition-photos/`, { method: "POST", body: form });
      push({ title: "Photo saved" });
      reload();
    } catch (err) {
      const data = err instanceof ApiError ? err.data : undefined;
      const fileErr = Array.isArray(data?.file) ? String(data?.file[0]) : null;
      push({ title: fileErr || (err instanceof ApiError ? err.message : "Upload failed"), tone: "err" });
    } finally {
      setUploading(null);
    }
  }

  async function saveOdometer() {
    try {
      await api(`/api/driver/pickups/${bookingId}/odometer/`, {
        method: "POST",
        body: JSON.stringify({ reading_km: Number(odometer) }),
      });
      push({ title: "Odometer reading saved" });
      setOdometer("");
      reload();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not save the reading", tone: "err" });
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-200 p-3 text-xs space-y-3 dark:border-zinc-700">
      <div>
        <span className="font-bold block">{stage === "PICKUP" ? "Condition photos before pickup" : "Condition photos at delivery"}</span>
        <span className="text-[11px] text-zinc-500">
          Photograph every side in front of the customer. These protect both of you if damage is disputed.
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {CONDITION_ANGLES.map((a) => (
          <label
            key={a.value}
            className={`flex cursor-pointer items-center justify-center gap-1 rounded-xl border py-2 font-bold ${
              done.has(a.value)
                ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-400"
                : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700"
            }`}
          >
            {done.has(a.value) ? <CheckCircle2 size={13} /> : <Camera size={13} />}
            {uploading === a.value ? "Uploading..." : a.label}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              className="hidden"
              disabled={uploading !== null}
              onChange={(e) => {
                void upload(a.value, e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Gauge size={16} className="text-zinc-400 shrink-0" />
        <input
          type="number"
          min={0}
          inputMode="numeric"
          placeholder={savedReading != null ? `Saved: ${savedReading} km` : "Odometer reading (km)"}
          className="min-w-0 flex-1 rounded-xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
          value={odometer}
          onChange={(e) => setOdometer(e.target.value)}
        />
        <button
          type="button"
          disabled={!odometer}
          onClick={saveOdometer}
          className="rounded-xl bg-zinc-800 px-3 py-2 font-bold text-white disabled:opacity-40 dark:bg-zinc-200 dark:text-zinc-900"
        >
          Save
        </button>
      </div>
    </div>
  );
}
