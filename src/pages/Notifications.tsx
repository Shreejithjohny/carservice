import { useEffect } from "react";
import { useApp } from "../context";

export function Notifications() {
  const { notifications, markNotificationsRead } = useApp();

  useEffect(() => {
    const t = setTimeout(markNotificationsRead, 800);
    return () => clearTimeout(t);
  }, [markNotificationsRead]);

  if (notifications.length === 0) {
    return (
      <div className="card empty">
        <p>No notifications yet. Booking and workshop updates will show up here.</p>
      </div>
    );
  }

  return (
    <div className="grid">
      {notifications.map((n) => (
        <article className="card" key={n.id} style={{ opacity: n.read ? 0.75 : 1 }}>
          <div className="pill">{n.time}</div>
          <h2 style={{ fontSize: 18, margin: "8px 0 4px" }}>{n.title}</h2>
          <p style={{ color: "var(--muted)" }}>{n.body}</p>
        </article>
      ))}
    </div>
  );
}
