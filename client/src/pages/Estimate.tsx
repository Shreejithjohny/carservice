import { FormEvent, useState } from "react";
import { api } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { EstimateResult } from "../types";

export function Estimate() {
  const { push } = useToast();
  const [brand, setBrand] = useState("Maruti");
  const [model, setModel] = useState("Swift");
  const [year, setYear] = useState(2019);
  const [fuelType, setFuelType] = useState("Petrol");
  const [problem, setProblem] = useState("There is a strange noise coming from the brakes and the vehicle vibrates while braking.");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<EstimateResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (problem.trim().length < 8) return push({ title: "Describe the problem", tone: "err" });
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("brand", brand);
      fd.append("model", model);
      fd.append("year", String(year));
      fd.append("fuelType", fuelType);
      fd.append("problem", problem);
      if (file) fd.append("image", file);
      const res = await api<EstimateResult>("/api/estimator", { method: "POST", body: fd });
      setResult(res);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form className="glass space-y-3 rounded-3xl p-6" onSubmit={onSubmit}>
        <div className="grid gap-2 sm:grid-cols-2">
          <input className="rounded-2xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="Brand" />
          <input className="rounded-2xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model" />
          <input type="number" className="rounded-2xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          <select className="rounded-2xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={fuelType} onChange={(e) => setFuelType(e.target.value)}>
            {["Petrol", "Diesel", "CNG", "Electric", "Hybrid"].map((f) => <option key={f}>{f}</option>)}
          </select>
        </div>
        <textarea className="min-h-28 w-full rounded-2xl border border-zinc-200 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={problem} onChange={(e) => setProblem(e.target.value)} />
        <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button disabled={busy} className="w-full rounded-2xl bg-[#ff4d2e] py-3 font-semibold text-white" type="submit">{busy ? "Estimating…" : "Get AI estimate"}</button>
      </form>
      {result ? (
        <div className="rounded-3xl bg-gradient-to-br from-zinc-900 to-zinc-800 p-6 text-white shadow-2xl">
          <p className="text-xs uppercase tracking-widest text-[#ffb020]">Possible issue</p>
          <h2 className="mt-1 text-2xl font-extrabold">{result.possibleIssue}</h2>
          <p className="mt-4 text-sm text-white/60">Recommended</p>
          <p className="text-lg font-semibold">{result.recommendedService}</p>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-white/10 p-4">
              <p className="text-xs text-white/50">Cost range</p>
              <p className="text-xl font-bold">₹{result.estimatedCostMin.toLocaleString("en-IN")} – ₹{result.estimatedCostMax.toLocaleString("en-IN")}</p>
            </div>
            <div className="rounded-2xl bg-white/10 p-4">
              <p className="text-xs text-white/50">Time</p>
              <p className="text-xl font-bold">{result.estimatedHoursMin}–{result.estimatedHoursMax} hrs</p>
            </div>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full bg-[#ff4d2e]" style={{ width: `${result.confidence}%` }} />
          </div>
          <p className="mt-1 text-sm text-white/70">{result.confidence}% confidence</p>
          <p className="mt-4 text-sm text-white/80">{result.suggestedNextStep}</p>
        </div>
      ) : (
        <div className="glass grid place-items-center rounded-3xl p-10 text-zinc-500">Results appear as a dashboard card after you estimate.</div>
      )}
    </div>
  );
}
