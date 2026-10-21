import { Link } from "react-router-dom";
import { useApp } from "../context";

export function Vehicles() {
  const { vehicles } = useApp();

  return (
    <div className="grid">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <p style={{ color: "var(--muted)" }}>Manage cars used for booking and estimates.</p>
        <Link className="btn btn-primary" to="/app/vehicles/add">Add Vehicle</Link>
      </div>
      {vehicles.length === 0 ? (
        <div className="card empty">
          <p>No vehicles yet. Add one to book a service.</p>
        </div>
      ) : (
        vehicles.map((v) => (
          <div className="card vehicle-card" key={v.id}>
            <div>
              <div className="pill">{v.nickname}</div>
              <h2 className="display" style={{ margin: "8px 0 4px" }}>{v.make} {v.model}</h2>
              <p style={{ color: "var(--muted)" }}>{v.year} · {v.fuel} · {v.color}</p>
              <p style={{ marginTop: 6 }}>{v.registration}</p>
            </div>
            <div className="btn-row">
              <Link className="btn btn-primary" to={`/app/book?vehicle=${v.id}`}>Book Service</Link>
              <Link className="btn btn-ghost" to={`/app/estimate?vehicle=${v.id}`}>Estimate</Link>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
