import { FormEvent, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { SERVICE_TYPES, type ServiceType } from "../types";
import { useApp } from "../context";
import { estimateRepairCost, formatInrRange } from "../lib/estimator";

export function BookService() {
  const { vehicles, addBooking, estimatorPrefill } = useApp();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initialVehicle = params.get("vehicle") ?? estimatorPrefill?.vehicleId ?? vehicles[0]?.id ?? "";
  const [vehicleId, setVehicleId] = useState(initialVehicle);
  const [serviceType, setServiceType] = useState<ServiceType>(
    (estimatorPrefill?.serviceType as ServiceType) || "Repair",
  );
  const [problem, setProblem] = useState(estimatorPrefill?.problem ?? "");
  const [pickupDate, setPickupDate] = useState("2026-08-28");
  const [pickupSlot, setPickupSlot] = useState("10:00 AM – 12:00 PM");
  const [address, setAddress] = useState("12, 4th Cross, Indiranagar, Bengaluru");
  const [error, setError] = useState("");

  const vehicle = useMemo(() => vehicles.find((v) => v.id === vehicleId), [vehicles, vehicleId]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!vehicle) {
      setError("Select a vehicle first.");
      return;
    }
    const est = estimateRepairCost({
      make: vehicle.make,
      model: vehicle.model,
      year: vehicle.year,
      serviceType,
      problem,
    });
    addBooking({
      vehicleId,
      serviceType,
      problem: problem || serviceType,
      pickupDate,
      pickupSlot,
      address,
      estimatedCost: formatInrRange(est.costMin, est.costMax),
    });
    navigate("/app/track");
  }

  if (vehicles.length === 0) {
    return (
      <div className="card empty">
        <p>Add a vehicle before booking.</p>
        <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={() => navigate("/app/vehicles/add")}>
          Add Vehicle
        </button>
      </div>
    );
  }

  return (
    <form className="card grid" onSubmit={onSubmit} style={{ maxWidth: 720 }}>
      <div className="field">
        <label htmlFor="vehicle">Select vehicle</label>
        <select id="vehicle" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.nickname} — {v.make} {v.model} ({v.registration})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="stype">Service type</label>
        <select id="stype" value={serviceType} onChange={(e) => setServiceType(e.target.value as ServiceType)}>
          {SERVICE_TYPES.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="problem">Describe the problem</label>
        <textarea id="problem" value={problem} onChange={(e) => setProblem(e.target.value)} placeholder="What should the technician look at?" />
      </div>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="date">Pickup date</label>
          <input id="date" type="date" value={pickupDate} onChange={(e) => setPickupDate(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="slot">Pickup slot</label>
          <select id="slot" value={pickupSlot} onChange={(e) => setPickupSlot(e.target.value)}>
            <option>8:00 AM – 10:00 AM</option>
            <option>10:00 AM – 12:00 PM</option>
            <option>12:00 PM – 2:00 PM</option>
            <option>4:00 PM – 6:00 PM</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor="addr">Pickup address</label>
        <textarea id="addr" value={address} onChange={(e) => setAddress(e.target.value)} />
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      <button className="btn btn-primary" type="submit">Confirm booking</button>
    </form>
  );
}
