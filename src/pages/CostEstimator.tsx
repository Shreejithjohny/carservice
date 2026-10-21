import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { MAKES_MODELS, SERVICE_TYPES, type ServiceType } from "../types";
import { useApp } from "../context";
import type { CostEstimate } from "../types";
import { estimateRepairCost, formatHours, formatInrRange } from "../lib/estimator";

export function CostEstimator() {
  const { vehicles, setChatOpen, setEstimatorPrefill } = useApp();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const makes = Object.keys(MAKES_MODELS);

  const [vehicleId, setVehicleId] = useState(params.get("vehicle") ?? vehicles[0]?.id ?? "custom");
  const selected = vehicles.find((v) => v.id === vehicleId);

  const [make, setMake] = useState(selected?.make ?? makes[0]);
  const [model, setModel] = useState(selected?.model ?? MAKES_MODELS[makes[0]][0]);
  const [year, setYear] = useState(selected?.year ?? 2019);
  const [serviceType, setServiceType] = useState<ServiceType>("Brake Service");
  const [problem, setProblem] = useState(
    "There is a strange noise coming from the brakes and the vehicle vibrates while braking.",
  );
  const [estimate, setEstimate] = useState<ReturnType<typeof estimateRepairCost> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (selected) {
      setMake(selected.make);
      setModel(selected.model);
      setYear(selected.year);
    }
  }, [selected]);

  const years = useMemo(() => Array.from({ length: 32 }, (_, i) => 2026 - i), []);

  function onMake(next: string) {
    setMake(next);
    setModel(MAKES_MODELS[next][0]);
    setVehicleId("custom");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (problem.trim().length < 12) {
      setError("Please describe the problem in a bit more detail so we can estimate.");
      return;
    }
    setError("");
    setEstimate(
      estimateRepairCost({ make, model, year, serviceType, problem }),
    );
  }

  function bookThis(est: CostEstimate) {
    setEstimatorPrefill({
      vehicleId: selected?.id,
      serviceType,
      problem,
    });
    void est;
    navigate("/app/book");
  }

  return (
    <div className="grid grid-2">
      <form className="card grid" onSubmit={onSubmit}>
        <p style={{ color: "var(--muted)" }}>
          Get an approximate service or repair cost before you book.
        </p>
        <div className="field">
          <label htmlFor="veh">Select Vehicle</label>
          <select
            id="veh"
            value={vehicleId}
            onChange={(e) => {
              setVehicleId(e.target.value);
              const v = vehicles.find((x) => x.id === e.target.value);
              if (v) {
                setMake(v.make);
                setModel(v.model);
                setYear(v.year);
              }
            }}
          >
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.nickname} — {v.make} {v.model}
              </option>
            ))}
            <option value="custom">Enter make & model manually</option>
          </select>
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label htmlFor="make">Vehicle Make</label>
            <select id="make" value={make} onChange={(e) => onMake(e.target.value)}>
              {makes.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="model">Model</label>
            <select id="model" value={model} onChange={(e) => { setModel(e.target.value); setVehicleId("custom"); }}>
              {(MAKES_MODELS[make] ?? []).map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label htmlFor="year">Manufacturing Year</label>
            <select id="year" value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {years.map((y) => <option key={y}>{y}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="stype">Service Type</label>
            <select id="stype" value={serviceType} onChange={(e) => setServiceType(e.target.value as ServiceType)}>
              {SERVICE_TYPES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="problem">Describe the Problem</label>
          <textarea
            id="problem"
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
          />
        </div>
        {error && <p style={{ color: "var(--danger)", fontSize: 14 }}>{error}</p>}
        <button className="btn btn-gold" type="submit">Get AI Cost Estimate</button>
      </form>

      {estimate ? (
        <article className="card estimate-card">
          <h3>Possible Issue</h3>
          <p>{estimate.possibleIssue}</p>
          <h3>Recommended Service</h3>
          <p>{estimate.recommendedService}</p>
          <h3>Estimated Cost</h3>
          <p>{formatInrRange(estimate.costMin, estimate.costMax)}</p>
          <h3>Estimated Service Time</h3>
          <p>{formatHours(estimate.timeMinHours, estimate.timeMaxHours)}</p>
          <p className="disclaimer">
            This is an approximate AI-generated estimate. The final cost may vary after physical inspection of the vehicle.
          </p>
          <div className="btn-row" style={{ marginTop: 16 }}>
            <button className="btn btn-gold" type="button" onClick={() => bookThis(estimate)}>
              Book This Service
            </button>
            <button className="btn" type="button" style={{ background: "rgba(255,255,255,0.12)", color: "#fff" }} onClick={() => setEstimate(null)}>
              Modify Details
            </button>
            <button className="btn" type="button" style={{ background: "rgba(255,255,255,0.12)", color: "#fff" }} onClick={() => setChatOpen(true)}>
              Ask AI Assistant
            </button>
          </div>
        </article>
      ) : (
        <div className="card empty">
          <p>Your estimate card will appear here after you tap Get AI Cost Estimate.</p>
        </div>
      )}
    </div>
  );
}
