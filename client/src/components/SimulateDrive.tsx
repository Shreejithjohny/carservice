import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Play, Square } from "lucide-react";
import { api } from "../services/api";
import { pathKm, pointsAlong } from "../utils/geo";
import type { Booking } from "../types";

type LngLat = [number, number];

const STEP_EVERY_MS = 3000;
const TARGET_STEPS = 40; // about 2 minutes per drive, whatever its length

/** Where the drive starts and ends for the job's stage: workshop -> customer, or customer -> workshop. */
function legFor(booking: Booking): { from: LngLat; to: LngLat; toName: string } | null {
  const center = booking.service_center_details;
  if (booking.pickup_latitude == null || booking.pickup_longitude == null || center?.latitude == null || center?.longitude == null) return null;
  const customer: LngLat = [Number(booking.pickup_longitude), Number(booking.pickup_latitude)];
  const workshop: LngLat = [Number(center.longitude), Number(center.latitude)];
  return booking.status === "Vehicle Picked Up"
    ? { from: customer, to: workshop, toName: center.name || "the workshop" }
    : { from: workshop, to: customer, toName: "the customer" };
}

/**
 * Demo-mode only: drives the job's car along the road route by sending pretend GPS positions
 * (one every 3 seconds, about 2 minutes in all), so the customer's Track page can be shown moving
 * without a phone on the road. Uses the same endpoint as real GPS.
 */
export function SimulateDrive({ booking, onRunningChange }: Readonly<{ booking: Booking; onRunningChange: (running: boolean) => void }>) {
  const [state, setState] = useState<"idle" | "routing" | "driving" | "done" | "error">("idle");
  const [progress, setProgress] = useState({ step: 0, steps: 0, km: 0 });
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const run = useRef(0); // bumped on every start and stop, so a stopped run can't carry on
  const leg = legFor(booking);

  const stop = (next: "idle" | "done" | "error" = "idle") => {
    run.current += 1;
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    setState(next);
    onRunningChange(false);
  };

  // Stop sending when the page or the job card goes away
  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

  async function start() {
    if (!leg) return;
    const id = ++run.current;
    setMessage(null);
    setState("routing");
    onRunningChange(true);
    let path: LngLat[] = [leg.from, leg.to];
    try {
      const q = (p: LngLat) => `${p[1].toFixed(5)},${p[0].toFixed(5)}`;
      const road = await api<{ coordinates: LngLat[] }>(`/api/location/route/?from=${q(leg.from)}&to=${q(leg.to)}`);
      if (road.coordinates.length > 1) path = road.coordinates;
    } catch {
      setMessage("Road routing is unavailable, so the car drives in a straight line.");
    }
    if (id !== run.current) return; // stopped while the route was loading
    const km = pathKm(path);
    const points = pointsAlong(path, Math.max(50, (km * 1000) / TARGET_STEPS));
    let i = 0;
    setProgress({ step: 0, steps: points.length, km: Math.round(km * 10) / 10 });
    setState("driving");

    const sendNext = () => {
      const [longitude, latitude] = points[i];
      api(`/api/driver/pickups/${booking.id}/location/`, { method: "POST", body: JSON.stringify({ latitude, longitude }) }).catch(() => {
        setMessage("A position could not be sent; the simulation stopped.");
        stop("error");
      });
      i += 1;
      setProgress((p) => ({ ...p, step: i }));
      if (i >= points.length) stop("done");
    };
    sendNext();
    timer.current = setInterval(sendNext, STEP_EVERY_MS);
  }

  if (!leg) {
    return <p className="text-[11px] text-zinc-500">Simulated drive needs both the pickup point and the workshop on the map.</p>;
  }

  const running = state === "routing" || state === "driving";
  const pct = progress.steps ? Math.round((progress.step / progress.steps) * 100) : 0;
  return (
    <div className="space-y-2 rounded-2xl border border-dashed border-brand/50 p-3 text-xs">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="block font-bold">Demo: simulate the drive</span>
          <span className="text-[11px] text-zinc-500">
            Sends pretend GPS along the road to {leg.toName} (about 2 minutes), so the customer's Track page shows the car moving.
          </span>
        </div>
        <button
          type="button"
          onClick={() => (running ? stop() : void start())}
          className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 font-bold ${running ? "bg-red-500 text-white" : "bg-brand text-white hover:bg-brand-hover"}`}
        >
          {state === "routing" && <LoaderCircle size={14} className="animate-spin" />}
          {state === "driving" && <Square size={12} />}
          {!running && <Play size={12} />}
          {running ? "Stop simulation" : "Simulate drive"}
        </button>
      </div>
      {(state === "driving" || state === "done") && (
        <div className="space-y-1">
          <div className="h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${pct}%` }} />
          </div>
          {/* <output> is announced by screen readers as it changes */}
          <output className="block text-[11px] text-zinc-500">
            {state === "done" ? `Arrived: drove ${progress.km} km.` : `Driving… position ${progress.step} of ${progress.steps} · ${progress.km} km route`}
          </output>
        </div>
      )}
      {message && <p className="text-[11px] text-amber-700 dark:text-amber-400">{message}</p>}
    </div>
  );
}
