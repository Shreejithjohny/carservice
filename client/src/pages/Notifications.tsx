import { useState } from "react";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Bell, CheckCheck, Clock, CheckCircle2, ShieldAlert, Car, Wrench, Receipt, CalendarClock } from "lucide-react";
import type { NotificationItem } from "../types";

export function Notifications() {
  const { data, loading, error, reload } = useApi<NotificationItem[]>("/api/notifications/");
  const { push } = useToast();
  const [markingAll, setMarkingAll] = useState(false);

  async function markRead(id?: number | string) {
    if (!id) return;
    try {
      await api(`/api/notifications/${id}/read/`, { method: "PATCH" });
      reload();
    } catch {
      // ignore
    }
  }

  async function markAllRead() {
    setMarkingAll(true);
    try {
      await api("/api/notifications/mark-all-read/", { method: "POST" });
      push({ title: "All notifications marked as read", tone: "ok" });
      reload();
    } catch {
      push({ title: "Failed to mark all as read", tone: "err" });
    } finally {
      setMarkingAll(false);
    }
  }

  if (loading) return <Skeleton className="h-64" />;
  if (error) return <Empty title="Could not load notifications" hint={error} />;
  if (!data?.length) return <Empty title="No notifications yet" hint="Updates regarding your service, pickup, and invoice will appear here." />;

  const unreadCount = data.filter((n) => !n.is_read && !n.read).length;

  const getIcon = (type?: string) => {
    switch (type) {
      case "BOOKING_CREATED":
      case "BOOKING_CONFIRMED":
        return <Car className="h-4 w-4 text-blue-500" />;
      case "DRIVER_ASSIGNED":
      case "VEHICLE_PICKED_UP":
        return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "REPAIR_APPROVAL_REQUIRED":
        return <ShieldAlert className="h-4 w-4 text-[#ff4d2e]" />;
      case "SERVICE_STARTED":
      case "SERVICE_COMPLETED":
        return <Wrench className="h-4 w-4 text-amber-500" />;
      case "INVOICE_GENERATED":
        return <Receipt className="h-4 w-4 text-purple-500" />;
      case "SERVICE_REMINDER":
        return <CalendarClock className="h-4 w-4 text-amber-600" />;
      default:
        return <Bell className="h-4 w-4 text-[#ff4d2e]" />;
    }
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold flex items-center gap-2">
            <Bell className="text-[#ff4d2e]" /> Notifications
            {unreadCount > 0 && (
              <span className="rounded-full bg-[#ff4d2e] px-2.5 py-0.5 text-xs text-white">
                {unreadCount} new
              </span>
            )}
          </h1>
          <p className="text-sm text-zinc-500">Live lifecycle alerts and service updates</p>
        </div>

        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            disabled={markingAll}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
          >
            <CheckCheck className="h-3.5 w-3.5 text-emerald-500" />
            {markingAll ? "Marking..." : "Mark all as read"}
          </button>
        )}
      </div>

      <div className="space-y-3">
        {data.map((n) => {
          const isRead = n.is_read || n.read;
          const nid = n.id || n._id;
          return (
            <article
              key={nid}
              onClick={() => !isRead && markRead(nid)}
              className={`glass flex items-start gap-4 rounded-3xl p-5 transition cursor-pointer ${
                !isRead ? "border-l-4 border-l-[#ff4d2e] bg-[#ff4d2e]/5" : "opacity-80"
              }`}
            >
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white shadow-sm dark:bg-zinc-800">
                {getIcon(n.notification_type || n.type)}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#ff4d2e]">
                    {(n.notification_type || n.type || "ALERT").replace(/_/g, " ")}
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-zinc-400">
                    <Clock className="h-3 w-3" />
                    {new Date(n.created_at || n.createdAt || "").toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-zinc-900 dark:text-white mt-0.5">{n.title}</h3>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{n.message || n.body}</p>

                {n.booking_reference && (
                  <span className="inline-block mt-2 rounded-lg bg-zinc-100 px-2 py-0.5 text-[10px] font-mono text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    Ref: {n.booking_reference}
                  </span>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
