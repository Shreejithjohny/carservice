import { Link } from "react-router-dom";
import { useApp } from "../context";

export function Dashboard() {
  const { user, vehicles, bookings, notifications } = useApp();
  const live = bookings.find((b) => b.status !== "Delivered" && b.status !== "Cancelled");
  const unread = notifications.filter((n) => !n.read).length;

  return (
    <div className="grid">
      <p style={{ color: "var(--muted)" }}>Hello, {user?.name}. Here is a snapshot of your garage and jobs.</p>
      <div className="grid grid-3">
        <div className="card stat">
          <span>Vehicles</span>
          <b>{vehicles.length}</b>
        </div>
        <div className="card stat">
          <span>Active booking</span>
          <b>{live ? live.status : "None"}</b>
        </div>
        <div className="card stat">
          <span>Unread alerts</span>
          <b>{unread}</b>
        </div>
      </div>
      {live ? (
        <div className="card">
          <div className="pill live">In progress · {live.id}</div>
          <h2 className="display" style={{ margin: "10px 0" }}>{live.serviceType}</h2>
          <p style={{ color: "var(--muted)" }}>{live.problem}</p>
          <div className="btn-row" style={{ marginTop: 14 }}>
            <Link className="btn btn-primary" to="/app/track">Track Service</Link>
            <Link className="btn btn-ghost" to="/app/help">Ask AI about this job</Link>
          </div>
        </div>
      ) : (
        <div className="card empty">
          <p>No active service. Book a pickup or get an AI cost estimate first.</p>
          <div className="btn-row" style={{ justifyContent: "center", marginTop: 12 }}>
            <Link className="btn btn-primary" to="/app/book">Book Service</Link>
            <Link className="btn btn-ghost" to="/app/estimate">AI Cost Estimator</Link>
          </div>
        </div>
      )}
    </div>
  );
}
