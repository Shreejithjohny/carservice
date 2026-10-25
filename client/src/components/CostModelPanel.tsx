import { useState } from "react";
import { BrainCircuit, AlertTriangle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { CostModelStatus } from "../types";

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

/** Admin card: state and cross-validated accuracy of the learned repair-cost model, with a retrain button. */
export function CostModelPanel() {
  const { data, reload } = useApi<CostModelStatus>("/api/admin/cost-model/");
  const { push } = useToast();
  const [training, setTraining] = useState(false);

  async function train() {
    setTraining(true);
    try {
      await api("/api/admin/cost-model/train/", { method: "POST" });
      push({ title: "Cost model retrained" });
      reload();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Training failed", tone: "err" });
    } finally {
      setTraining(false);
    }
  }

  if (!data) return null;
  const m = data.active;
  const enough = data.available_samples >= data.min_samples;

  return (
    <section className="glass rounded-3xl p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-bold">
            <BrainCircuit size={18} className="text-brand-fg" /> Repair cost model
          </h3>
          <p className="text-xs text-zinc-500">
            {m
              ? `Active since ${new Date(m.trained_at).toLocaleString("en-IN")} · trained on ${m.n_samples} repairs`
              : `Not trained — estimates use the rule-based formula. ${data.available_samples} of ${data.min_samples} repairs needed.`}
          </p>
        </div>
        <button
          type="button"
          onClick={train}
          disabled={training || !enough}
          title={enough ? undefined : `Needs at least ${data.min_samples} completed, approved repairs`}
          className="rounded-xl bg-brand px-4 py-2 text-xs font-bold text-white disabled:opacity-40"
        >
          {training ? "Training..." : m ? `Retrain (${data.available_samples} repairs)` : "Train model"}
        </button>
      </div>

      {m && (
        <>
          {m.synthetic_share > 0 && (
            <p className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
              <AlertTriangle size={16} className="shrink-0" />
              {m.synthetic_share}% of the training repairs are synthetic demo data. These accuracy figures only show that the
              model recovers the generator&apos;s made-up prices — they are not evidence about real workshop costs.
            </p>
          )}
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-zinc-500">
                <th className="py-1 font-semibold">5-fold cross-validation</th>
                <th className="py-1 text-right font-semibold">Avg error (₹)</th>
                <th className="py-1 text-right font-semibold">Avg error (%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200/70 dark:divide-zinc-800">
              <tr>
                <td className="py-1.5 font-semibold">Learned model</td>
                <td className="py-1.5 text-right">{inr(m.metrics.ml.mae)}</td>
                <td className="py-1.5 text-right font-bold">{m.metrics.ml.mape}%</td>
              </tr>
              <tr>
                <td className="py-1.5">Rule-based formula</td>
                <td className="py-1.5 text-right">{inr(m.metrics.rule_based.mae)}</td>
                <td className="py-1.5 text-right">{m.metrics.rule_based.mape}%</td>
              </tr>
            </tbody>
          </table>
          <p className="text-xs text-zinc-500">
            {m.metrics.interval_coverage}% of held-out repairs fell inside their predicted 80% price range.
          </p>
        </>
      )}
    </section>
  );
}
