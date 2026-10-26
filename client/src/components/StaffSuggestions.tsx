import { Sparkles } from "lucide-react";
import { useApi } from "../hooks/useApi";

type DriverRow = { driver_id: number; name: string; distance_km: number | null; jobs_today: number; score: number; eligible: boolean; reason: string };
type MechanicRow = { mechanic_id: number; name: string; open_jobs: number; eligible: boolean; reason: string };

/**
 * Ranked staff suggestions for a booking: drivers by distance to the customer plus a 3 km penalty per
 * pickup already that day, mechanics by open jobs. Picking one only fills the dropdown; the manager saves.
 */
export function StaffSuggestions({
  bookingId,
  onPickDriver,
  onPickMechanic,
}: Readonly<{ bookingId: string | number; onPickDriver: (id: string) => void; onPickMechanic: (id: string) => void }>) {
  const { data } = useApi<{ drivers: DriverRow[]; mechanics: MechanicRow[] }>(`/api/service-center/bookings/${bookingId}/staff-suggestions/`);
  if (!data) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2 text-xs">
      <div>
        <p className="mb-1 flex items-center gap-1 font-bold text-zinc-500">
          <Sparkles size={13} className="text-brand-fg" /> Best drivers (distance + day's workload)
        </p>
        <ol className="space-y-1">
          {data.drivers.slice(0, 4).map((d, i) => (
            <li key={d.driver_id} className={`flex items-center justify-between gap-2 rounded-xl border px-2 py-1.5 ${d.eligible ? "border-zinc-200 dark:border-zinc-700" : "border-dashed border-zinc-200 opacity-60 dark:border-zinc-800"}`}>
              <span>
                <strong>{i === 0 && d.eligible ? "★ " : ""}{d.name}</strong>
                <span className="block text-[11px] text-zinc-500">{d.reason}{d.eligible ? ` · score ${d.score}` : ""}</span>
              </span>
              {d.eligible && (
                <button type="button" onClick={() => onPickDriver(String(d.driver_id))} className="rounded-lg bg-brand/10 px-2 py-1 font-bold text-brand-fg hover:bg-brand/20">
                  Pick
                </button>
              )}
            </li>
          ))}
          {!data.drivers.length && <li className="text-zinc-500">No drivers at this center.</li>}
        </ol>
      </div>
      <div>
        <p className="mb-1 flex items-center gap-1 font-bold text-zinc-500">
          <Sparkles size={13} className="text-brand-fg" /> Least busy mechanics
        </p>
        <ol className="space-y-1">
          {data.mechanics.slice(0, 4).map((m, i) => (
            <li key={m.mechanic_id} className={`flex items-center justify-between gap-2 rounded-xl border px-2 py-1.5 ${m.eligible ? "border-zinc-200 dark:border-zinc-700" : "border-dashed border-zinc-200 opacity-60 dark:border-zinc-800"}`}>
              <span>
                <strong>{i === 0 && m.eligible ? "★ " : ""}{m.name}</strong>
                <span className="block text-[11px] text-zinc-500">{m.reason}</span>
              </span>
              {m.eligible && (
                <button type="button" onClick={() => onPickMechanic(String(m.mechanic_id))} className="rounded-lg bg-brand/10 px-2 py-1 font-bold text-brand-fg hover:bg-brand/20">
                  Pick
                </button>
              )}
            </li>
          ))}
          {!data.mechanics.length && <li className="text-zinc-500">No mechanics at this center.</li>}
        </ol>
      </div>
    </div>
  );
}
