import { useState, FormEvent } from "react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Sparkles, AlertCircle, X, Clock } from "lucide-react";
import type { Vehicle, ServiceType, RepairCostEstimate } from "../types";

interface Props {
  vehicleId?: number | string;
  vehicles?: Vehicle[];
  serviceTypes?: ServiceType[];
  initialIssue?: string;
  initialSeverity?: string;
  onClose?: () => void;
  onApplyEstimate?: (est: RepairCostEstimate) => void;
}

export function AICostEstimatorModal({
  vehicleId,
  vehicles = [],
  serviceTypes = [],
  initialIssue = "",
  initialSeverity = "MEDIUM",
  onClose,
  onApplyEstimate,
}: Props) {
  const { push } = useToast();

  const [selectedVehicle, setSelectedVehicle] = useState<number | string>(vehicleId || (vehicles[0]?.id ?? ""));
  const [selectedServiceType, setSelectedServiceType] = useState<string>("");
  const [issueDescription, setIssueDescription] = useState(initialIssue);
  const [severity, setSeverity] = useState(initialSeverity);
  const [laborHours, setLaborHours] = useState("1.5");
  const [loading, setLoading] = useState(false);
  const [estimate, setEstimate] = useState<RepairCostEstimate | null>(null);

  async function handleEstimate(e: FormEvent) {
    e.preventDefault();
    if (!selectedVehicle) {
      push({ title: "Please select a vehicle", tone: "err" });
      return;
    }
    if (issueDescription.trim().length < 5) {
      push({ title: "Please provide a detailed issue description", tone: "err" });
      return;
    }

    setLoading(true);
    try {
      const res = await api<RepairCostEstimate>("/api/repair-cost/estimate/", {
        method: "POST",
        body: JSON.stringify({
          vehicle: Number(selectedVehicle),
          service_type: selectedServiceType ? Number(selectedServiceType) : null,
          issue_description: issueDescription.trim(),
          severity,
          estimated_labor_hours: parseFloat(laborHours) || 1.5,
        }),
      });
      setEstimate(res);
      push({ title: "Cost estimate generated", tone: "ok" });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to generate estimate";
      push({ title: `Estimation Error: ${msg}`, tone: "err" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="relative max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-3xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-900">
        {onClose && (
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full p-2 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        )}

        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand/10 text-brand-fg">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold">Repair Cost Estimator</h2>
            <p className="text-xs text-zinc-500">Instant estimate from service price, severity, labour and fuel type</p>
          </div>
        </div>

        <form onSubmit={handleEstimate} className="space-y-4">
          {!vehicleId && vehicles.length > 0 && (
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Select Vehicle
              </label>
              <select
                value={selectedVehicle}
                onChange={(e) => setSelectedVehicle(e.target.value)}
                className="w-full rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.brand} {v.model} ({v.registration_number}) - {v.fuel_type}
                  </option>
                ))}
              </select>
            </div>
          )}

          {serviceTypes.length > 0 && (
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Related Service Package (Optional)
              </label>
              <select
                value={selectedServiceType}
                onChange={(e) => setSelectedServiceType(e.target.value)}
                className="w-full rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                <option value="">General Repair / Standalone</option>
                {serviceTypes.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.name} (Base: ₹{st.base_price})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Issue or Symptom Description
            </label>
            <textarea
              rows={3}
              value={issueDescription}
              onChange={(e) => setIssueDescription(e.target.value)}
              placeholder="Describe the vehicle issue (e.g., Brake pedal feels spongy and grinding sound while stopping)"
              className="w-full rounded-2xl border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Issue Severity
              </label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="w-full rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              >
                <option value="LOW">Low (Minor / Wear)</option>
                <option value="MEDIUM">Medium (Routine fix)</option>
                <option value="HIGH">High (Safety risk)</option>
                <option value="CRITICAL">Critical (Immediate danger)</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Est. Labor Hours
              </label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="24"
                value={laborHours}
                onChange={(e) => setLaborHours(e.target.value)}
                className="w-full rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-brand py-3 text-sm font-bold text-white shadow-lg shadow-brand/20 transition hover:bg-brand-hover disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            {loading ? "Calculating..." : "Calculate Cost Estimate"}
          </button>
        </form>

        {estimate && (
          <div className="mt-5 space-y-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/60">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-brand-fg">
                {estimate.estimation_source === "ML" ? "Learned from past repairs" : estimate.estimation_source === "AI" ? "AI Estimate" : "Rule-based estimate"}
              </span>
              <span className="flex items-center gap-1 text-xs text-zinc-500">
                <Clock className="h-3.5 w-3.5" /> ~{estimate.estimated_labor_hours} hrs labor
              </span>
            </div>

            <div>
              <p className="text-xs text-zinc-500">Estimated Cost Range</p>
              <p className="text-2xl font-black text-zinc-900 dark:text-white">
                ₹{Number(estimate.estimated_min_cost).toLocaleString("en-IN")} – ₹
                {Number(estimate.estimated_max_cost).toLocaleString("en-IN")}
              </p>
            </div>

            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
              {estimate.explanation}
            </p>

            <div className="flex items-start gap-2 rounded-xl bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                <strong>Estimate — Not Final Price.</strong> Final price may vary based on actual physical
                inspection and service-center pricing.
              </span>
            </div>

            {onApplyEstimate && (
              <button
                type="button"
                onClick={() => {
                  onApplyEstimate(estimate);
                  if (onClose) onClose();
                }}
                className="w-full rounded-xl bg-zinc-900 py-2 text-xs font-semibold text-white hover:bg-black dark:bg-zinc-100 dark:text-black dark:hover:bg-white"
              >
                Use Estimate in Repair Request
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
