import { useEffect, useState } from "react";
import { ProgressRing } from "../components/ProgressRing";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { Activity, Car, Wrench, Info } from "lucide-react";
import type { Vehicle, CarHealthScore, Booking } from "../types";

export function Health() {
  const { data: vehicles, loading: loadingVehicles } = useApi<Vehicle[]>("/api/vehicles/");
  const { data: bookings } = useApi<Booking[]>("/api/bookings/");

  const [selectedVehicleId, setSelectedVehicleId] = useState<string | number>("");
  const [healthScore, setHealthScore] = useState<CarHealthScore | null>(null);
  const [loadingScore, setLoadingScore] = useState(false);

  // Set default vehicle when loaded
  useEffect(() => {
    if (vehicles && vehicles.length > 0 && !selectedVehicleId) {
      setSelectedVehicleId(vehicles[0].id || "");
    }
  }, [vehicles, selectedVehicleId]);

  // Fetch health score when selectedVehicleId changes
  useEffect(() => {
    if (!selectedVehicleId) return;

    let isMounted = true;
    setLoadingScore(true);
    api<CarHealthScore>(`/api/vehicles/${selectedVehicleId}/health-score/`)
      .then((res) => {
        if (isMounted) setHealthScore(res);
      })
      .catch(() => {
        if (isMounted) setHealthScore(null);
      })
      .finally(() => {
        if (isMounted) setLoadingScore(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedVehicleId]);

  if (loadingVehicles) return <Skeleton className="h-80" />;
  if (!vehicles?.length) {
    return <Empty title="No vehicles registered" hint="Add your vehicle in the Vehicles section to view its Car Health Score." />;
  }

  const selectedVehicle = vehicles.find((v) => String(v.id) === String(selectedVehicleId)) || vehicles[0];

  const getComplianceColor = (compliance: string) => {
    switch (compliance) {
      case "Excellent":
        return "text-emerald-600 bg-emerald-500/10 border-emerald-500/20";
      case "Good":
        return "text-blue-600 bg-blue-500/10 border-blue-500/20";
      case "Fair":
        return "text-amber-600 bg-amber-500/10 border-amber-500/20";
      case "Needs Attention":
        return "text-orange-600 bg-orange-500/10 border-orange-500/20";
      default:
        return "text-rose-600 bg-rose-500/10 border-rose-500/20";
    }
  };

  const vehicleHistory = (bookings || []).filter(
    (b) => String(b.vehicle) === String(selectedVehicleId) || String(b.vehicle_details?.id) === String(selectedVehicleId)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold flex items-center gap-2">
            <Activity className="text-[#ff4d2e]" /> Car Health Score
          </h1>
          <p className="text-sm text-zinc-500">Algorithmic vehicle health monitoring based on service history and inspections</p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Select Vehicle:</label>
          <select
            className="rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm font-semibold shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
            value={selectedVehicleId}
            onChange={(e) => setSelectedVehicleId(e.target.value)}
          >
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.brand} {v.model} ({v.registration_number})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loadingScore ? (
        <Skeleton className="h-72" />
      ) : healthScore ? (
        <>
          {/* Main Health Card */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="glass col-span-1 flex flex-col items-center justify-center rounded-3xl p-6 text-center">
              <ProgressRing value={healthScore.score} label="Health Index" />
              <div className="mt-4">
                <span
                  className={`inline-block rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider ${getComplianceColor(
                    healthScore.maintenance_compliance
                  )}`}
                >
                  Condition: {healthScore.maintenance_compliance}
                </span>
                <p className="mt-2 text-xs text-zinc-500">
                  Calculated: {new Date(healthScore.calculated_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            <div className="glass col-span-2 flex flex-col justify-between rounded-3xl p-6">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2">
                  <Car className="text-[#ff4d2e] h-5 w-5" />
                  {selectedVehicle.brand} {selectedVehicle.model} ({selectedVehicle.registration_number})
                </h3>
                <p className="text-xs text-zinc-500 mt-1">
                  Fuel: {selectedVehicle.fuel_type} · Year: {selectedVehicle.year} · Variant: {selectedVehicle.variant_name || "Standard"}
                </p>

                <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="rounded-2xl bg-zinc-50 p-3 text-center dark:bg-zinc-800/60">
                    <p className="text-[10px] uppercase font-bold text-zinc-400">Completed Services</p>
                    <p className="text-xl font-black text-emerald-600 mt-1">{healthScore.service_count}</p>
                  </div>
                  <div className="rounded-2xl bg-zinc-50 p-3 text-center dark:bg-zinc-800/60">
                    <p className="text-[10px] uppercase font-bold text-zinc-400">Resolved Repairs</p>
                    <p className="text-xl font-black text-blue-600 mt-1">{healthScore.resolved_issue_count}</p>
                  </div>
                  <div className="rounded-2xl bg-zinc-50 p-3 text-center dark:bg-zinc-800/60">
                    <p className="text-[10px] uppercase font-bold text-zinc-400">Warning Issues</p>
                    <p className="text-xl font-black text-amber-600 mt-1">{healthScore.warning_issue_count}</p>
                  </div>
                  <div className="rounded-2xl bg-zinc-50 p-3 text-center dark:bg-zinc-800/60">
                    <p className="text-[10px] uppercase font-bold text-zinc-400">Critical Issues</p>
                    <p className="text-xl font-black text-rose-600 mt-1">{healthScore.critical_issue_count}</p>
                  </div>
                </div>
              </div>

              <div className="mt-5 rounded-2xl border border-zinc-200/80 bg-zinc-50/50 p-4 text-xs dark:border-zinc-800 dark:bg-zinc-800/40">
                <p className="font-bold text-zinc-700 dark:text-zinc-300 mb-1 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-[#ff4d2e]" /> Algorithm Explanation & Contributing Factors:
                </p>
                <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  {healthScore.explanation}
                </p>
              </div>
            </div>
          </div>

          {/* Service History Summary */}
          <div className="glass rounded-3xl p-6">
            <h3 className="text-base font-bold flex items-center gap-2 mb-4">
              <Wrench className="h-5 w-5 text-[#ff4d2e]" /> Service History Log
            </h3>
            {!vehicleHistory.length ? (
              <p className="text-xs text-zinc-500 py-3">No completed services recorded yet for this vehicle.</p>
            ) : (
              <div className="divide-y divide-zinc-200/60 dark:divide-zinc-800">
                {vehicleHistory.map((h) => (
                  <div key={h.id} className="py-3 flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-zinc-900 dark:text-white">
                        {h.service_type_details?.name || "Doorstep Service"}
                      </p>
                      <p className="text-zinc-500 text-[11px]">
                        Ref: {h.booking_reference} · Date: {h.preferred_date || "Recent"}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="rounded-full bg-zinc-100 dark:bg-zinc-800 px-2.5 py-1 font-semibold text-zinc-700 dark:text-zinc-300">
                        {h.status}
                      </span>
                      {h.estimated_cost && (
                        <p className="mt-1 font-mono font-bold text-zinc-800 dark:text-zinc-200">
                          ₹{Number(h.estimated_cost).toFixed(2)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        <Empty title="Health score pending" hint="Health score will be calculated once this vehicle undergoes its first inspection or service." />
      )}
    </div>
  );
}
