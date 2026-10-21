import { useApp } from "../context";

export function ServiceHistory() {
  const { bookings, vehicles } = useApp();
  const done = bookings.filter((b) => b.status === "Delivered" || b.status === "Cancelled");

  if (done.length === 0) {
    return (
      <div className="card empty">
        <p>No completed or cancelled jobs yet. Active work appears under Track Service.</p>
      </div>
    );
  }

  return (
    <div className="grid">
      {done.map((b) => {
        const v = vehicles.find((x) => x.id === b.vehicleId);
        return (
          <article className="card" key={b.id}>
            <div className={`pill ${b.status === "Cancelled" ? "warn" : "ok"}`}>{b.status}</div>
            <h2 className="display" style={{ margin: "8px 0 4px" }}>{b.serviceType}</h2>
            <p style={{ color: "var(--muted)" }}>
              {b.id} · {v ? `${v.make} ${v.model}` : "Vehicle"} · {b.pickupDate}
            </p>
            <p style={{ marginTop: 8 }}>{b.problem}</p>
            <p style={{ marginTop: 8 }}>Final / estimated: {b.estimatedCost}</p>
          </article>
        );
      })}
    </div>
  );
}
