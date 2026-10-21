import { useApp } from "../context";

export function Profile() {
  const { user, vehicles, bookings } = useApp();

  return (
    <div className="grid" style={{ maxWidth: 640 }}>
      <div className="card">
        <h2 className="display" style={{ marginBottom: 8 }}>{user?.name}</h2>
        <p>{user?.phone}</p>
        <p style={{ color: "var(--muted)" }}>{user?.email || "No email on file"}</p>
      </div>
      <div className="card grid grid-2">
        <div className="stat">
          <span>Vehicles</span>
          <b>{vehicles.length}</b>
        </div>
        <div className="stat">
          <span>Bookings</span>
          <b>{bookings.length}</b>
        </div>
      </div>
      <div className="card">
        <h3 style={{ marginBottom: 8 }}>Preferences</h3>
        <p style={{ color: "var(--muted)" }}>
          Doorstep pickup is on. WhatsApp-style status alerts are simulated in Notifications for this demo.
        </p>
      </div>
    </div>
  );
}
