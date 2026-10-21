import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MAKES_MODELS } from "../types";
import { useApp } from "../context";

export function AddVehicle() {
  const { addVehicle } = useApp();
  const navigate = useNavigate();
  const makes = Object.keys(MAKES_MODELS);
  const [make, setMake] = useState(makes[0]);
  const [model, setModel] = useState(MAKES_MODELS[makes[0]][0]);
  const [year, setYear] = useState(2020);
  const [nickname, setNickname] = useState("");
  const [registration, setRegistration] = useState("");
  const [fuel, setFuel] = useState<"Petrol" | "Diesel" | "CNG" | "Electric" | "Hybrid">("Petrol");
  const [color, setColor] = useState("");
  const [error, setError] = useState("");

  function onMake(next: string) {
    setMake(next);
    setModel(MAKES_MODELS[next][0]);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!registration.trim()) {
      setError("Registration number is required.");
      return;
    }
    addVehicle({
      nickname: nickname.trim() || `${make} ${model}`,
      make,
      model,
      year,
      registration: registration.trim().toUpperCase(),
      fuel,
      color: color.trim() || "Unspecified",
    });
    navigate("/app/vehicles");
  }

  return (
    <form className="card grid" onSubmit={onSubmit} style={{ maxWidth: 640 }}>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="make">Make</label>
          <select id="make" value={make} onChange={(e) => onMake(e.target.value)}>
            {makes.map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="model">Model</label>
          <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
            {MAKES_MODELS[make].map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="year">Year</label>
          <input id="year" type="number" min={1995} max={2026} value={year} onChange={(e) => setYear(Number(e.target.value))} />
        </div>
        <div className="field">
          <label htmlFor="fuel">Fuel</label>
          <select id="fuel" value={fuel} onChange={(e) => setFuel(e.target.value as typeof fuel)}>
            <option>Petrol</option>
            <option>Diesel</option>
            <option>CNG</option>
            <option>Electric</option>
            <option>Hybrid</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor="reg">Registration</label>
        <input id="reg" value={registration} onChange={(e) => setRegistration(e.target.value)} placeholder="KA 05 MJ 2148" />
      </div>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="nick">Nickname</label>
          <input id="nick" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="Family Swift" />
        </div>
        <div className="field">
          <label htmlFor="color">Color</label>
          <input id="color" value={color} onChange={(e) => setColor(e.target.value)} />
        </div>
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      <div className="btn-row">
        <button className="btn btn-primary" type="submit">Save vehicle</button>
        <Link className="btn btn-ghost" to="/app/vehicles">Cancel</Link>
      </div>
    </form>
  );
}
