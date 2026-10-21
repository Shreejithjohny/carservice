import { useMemo, useState } from "react";
import { useApp } from "../context";
import type { BookingStatus } from "../types";

const STEPS: BookingStatus[] = [
  "Requested",
  "Driver Assigned",
  "Picked Up",
  "In Service",
  "Ready for Delivery",
  "Out for Delivery",
  "Delivered",
];

export function TrackService() {
  const { bookings, vehicles, cancelBooking } = useApp();
  const active = bookings.filter((b) => b.status !== "Delivered");
  const [id, setId] = useState(active[0]?.id ?? bookings[0]?.id ?? "");
  const booking = useMemo(() => bookings.find((b) => b.id === id), [bookings, id]);
  const vehicle = vehicles.find((v) => v.id === booking?.vehicleId);

  if (!booking) {
    return (
      <div className="card empty">
        <p>No bookings to track yet. Book a service to see live status.</p>
      </div>
    );
  }

  const idx = STEPS.indexOf(booking.status);
  const canCancel = booking.status === "Requested" || booking.status === "Driver Assigned";

  return (
    <div className="grid">
      {bookings.length > 1 && (
        <div className="field" style={{ maxWidth: 360 }}>
          <label htmlFor="bk">Select booking</label>
          <select id="bk" value={id} onChange={(e) => setId(e.target.value)}>
            {bookings.map((b) => (
              <option key={b.id} value={b.id}>
                {b.id} · {b.status}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="card">
        <div className={`pill ${booking.status === "Cancelled" ? "warn" : booking.status === "In Service" ? "live" : "ok"}`}>
          {booking.status}
        </div>
        <h2 className="display" style={{ margin: "10px 0 4px" }}>{booking.serviceType}</h2>
        <p style={{ color: "var(--muted)" }}>
          {vehicle ? `${vehicle.make} ${vehicle.model} · ${vehicle.registration}` : "Vehicle"} · {booking.id}
        </p>
        <p style={{ marginTop: 10 }}>{booking.problem}</p>
        <p style={{ marginTop: 8, color: "var(--muted)" }}>
          Pickup {booking.pickupDate} · {booking.pickupSlot}
        </p>
        <p>Estimate {booking.estimatedCost}</p>
      </div>
      {booking.status !== "Cancelled" && (
        <div className="card">
          <h3 className="display" style={{ marginBottom: 16 }}>Status timeline</h3>
          <div className="timeline">
            {STEPS.map((step, i) => (
              <div className="tl-item" key={step} style={{ paddingBottom: 16 }}>
                <span className={`tl-dot ${i <= idx ? "on" : ""}`} />
                <div>
                  <strong>{step}</strong>
                  {step === "In Service" && i === idx && (
                    <p style={{ color: "var(--muted)", fontSize: 14 }}>
                      The technician is working on the requested service. You will receive a notification once it is ready for delivery.
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {canCancel && (
        <button className="btn btn-danger" onClick={() => cancelBooking(booking.id)}>
          Cancel booking
        </button>
      )}
    </div>
  );
}
