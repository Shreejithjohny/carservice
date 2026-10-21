import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton, Empty } from "../components/States";
import { Building2 } from "lucide-react";
import type { Booking, User } from "../types";

const STATUS_TABS = [
  "All",
  "Pending",
  "Confirmed",
  "Pickup Scheduled",
  "Vehicle Picked Up",
  "In Service",
  "Ready for Delivery",
  "Completed",
  "Cancelled",
];

export function ServiceCenterDashboard() {
  const { data: bookings, loading, reload } = useApi<Booking[]>("/api/service-center/bookings/");
  const { data: employees } = useApi<{ drivers: User[]; mechanics: User[] }>("/api/service-center/employees/");
  const { push } = useToast();

  const [activeTab, setActiveTab] = useState("All");
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [driverId, setDriverId] = useState<string>("");
  const [mechanicId, setMechanicId] = useState<string>("");
  const [updating, setUpdating] = useState(false);

  const filteredBookings = (bookings || []).filter((b) => {
    if (activeTab === "All") return true;
    return b.status?.toLowerCase() === activeTab.toLowerCase();
  });

  const counts = (bookings || []).reduce<Record<string, number>>((acc, b) => {
    const s = b.status || "Pending";
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {});

  async function handleAssignAndStatus(booking: Booking, newStatus?: string) {
    setUpdating(true);
    try {
      const payload: Record<string, unknown> = {};
      if (newStatus) payload.status = newStatus;
      if (driverId) payload.assigned_driver_id = driverId;
      if (mechanicId) payload.assigned_mechanic_id = mechanicId;

      await api(`/api/service-center/bookings/${booking.id || booking._id || booking.booking_reference}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      push({ title: "Booking updated successfully" });
      setSelectedBooking(null);
      setDriverId("");
      setMechanicId("");
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to update booking";
      push({ title: msg, tone: "err" });
    } finally {
      setUpdating(false);
    }
  }

  if (loading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Building2 className="text-[#ff4d2e]" /> Service Center Dashboard
        </h1>
        <p className="text-sm text-zinc-500">Manage incoming service bookings, assign valets and mechanics.</p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="glass rounded-2xl p-4 border border-amber-200 dark:border-amber-900/30">
          <p className="text-xs font-bold text-amber-600 dark:text-amber-400 uppercase">Pending Requests</p>
          <p className="text-2xl font-black mt-1">{counts["Pending"] || 0}</p>
        </div>
        <div className="glass rounded-2xl p-4 border border-blue-200 dark:border-blue-900/30">
          <p className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase">Confirmed & Pickups</p>
          <p className="text-2xl font-black mt-1">{(counts["Confirmed"] || 0) + (counts["Pickup Scheduled"] || 0)}</p>
        </div>
        <div className="glass rounded-2xl p-4 border border-purple-200 dark:border-purple-900/30">
          <p className="text-xs font-bold text-purple-600 dark:text-purple-400 uppercase">In Service</p>
          <p className="text-2xl font-black mt-1">{counts["In Service"] || 0}</p>
        </div>
        <div className="glass rounded-2xl p-4 border border-emerald-200 dark:border-emerald-900/30">
          <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase">Completed</p>
          <p className="text-2xl font-black mt-1">{counts["Completed"] || 0}</p>
        </div>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-zinc-200/80 pb-3 dark:border-zinc-800">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-2xl px-3.5 py-1.5 text-xs font-bold transition ${
              activeTab === tab
                ? "bg-[#ff4d2e] text-white"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Bookings List */}
      {!filteredBookings.length ? (
        <Empty title="No bookings found" hint="No service requests match the selected status filter." />
      ) : (
        <div className="space-y-4">
          {filteredBookings.map((b) => {
            const bId = b.id || b._id || b.booking_reference;
            const isSelected = selectedBooking?.id === b.id;

            return (
              <div key={bId} className="glass rounded-3xl p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800 pb-3">
                  <div>
                    <span className="text-xs font-mono font-bold text-[#ff4d2e] bg-[#ff4d2e]/10 px-2.5 py-0.5 rounded-full">
                      {b.booking_reference || b.booking_id}
                    </span>
                    <h3 className="text-lg font-bold mt-1">
                      {b.service_type_details?.name || b.serviceType || "Vehicle Service"}
                    </h3>
                    <p className="text-xs text-zinc-500">
                      Customer: <strong>{b.customer_name || b.customer_email || "Customer"}</strong> {b.customer_phone ? `(${b.customer_phone})` : ""}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="rounded-full bg-[#ff4d2e]/15 px-3 py-1 text-xs font-bold text-[#ff4d2e]">
                      {b.status}
                    </span>
                    <p className="text-sm font-extrabold text-emerald-600 mt-1">
                      ₹{Number(b.estimated_cost || b.estimatedCost || 0).toLocaleString("en-IN")}
                    </p>
                  </div>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-zinc-400 font-bold block mb-0.5">Vehicle</span>
                    <p className="font-semibold">
                      {b.vehicle_details ? `${b.vehicle_details.brand} ${b.vehicle_details.model}` : "Vehicle"} · {b.vehicle_details?.registration_number || ""}
                    </p>
                  </div>
                  <div>
                    <span className="text-zinc-400 font-bold block mb-0.5">Pickup Location</span>
                    <p className="font-medium truncate">{b.pickup_address || b.address || "Address shared"}</p>
                  </div>
                  <div>
                    <span className="text-zinc-400 font-bold block mb-0.5">Assigned Staff</span>
                    <p className="font-semibold text-zinc-700 dark:text-zinc-300">
                      Valet: {b.assigned_driver_details?.name || "Unassigned"} · Mech: {b.assigned_mechanic_details?.name || "Unassigned"}
                    </p>
                  </div>
                </div>

                {/* Action Toolbar */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                  <div className="flex gap-2">
                    {b.status === "Pending" && (
                      <>
                        <button
                          onClick={() => handleAssignAndStatus(b, "Confirmed")}
                          className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-700"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => handleAssignAndStatus(b, "Cancelled")}
                          className="rounded-xl bg-red-500 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-red-600"
                        >
                          Reject
                        </button>
                      </>
                    )}

                    {b.status === "Confirmed" && (
                      <button
                        onClick={() => handleAssignAndStatus(b, "Pickup Scheduled")}
                        className="rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
                      >
                        Schedule Pickup
                      </button>
                    )}

                    {b.status === "Vehicle Picked Up" && (
                      <button
                        onClick={() => handleAssignAndStatus(b, "In Service")}
                        className="rounded-xl bg-purple-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-purple-700"
                      >
                        Start Service
                      </button>
                    )}

                    {b.status === "In Service" && (
                      <button
                        onClick={() => handleAssignAndStatus(b, "Ready for Delivery")}
                        className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-700"
                      >
                        Mark Ready for Delivery
                      </button>
                    )}

                    {b.status === "Ready for Delivery" && (
                      <button
                        onClick={() => handleAssignAndStatus(b, "Completed")}
                        className="rounded-xl bg-emerald-700 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-800"
                      >
                        Complete Order
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => {
                      if (isSelected) {
                        setSelectedBooking(null);
                      } else {
                        setSelectedBooking(b);
                        setDriverId(String(b.assigned_driver || ""));
                        setMechanicId(String(b.assigned_mechanic || ""));
                      }
                    }}
                    className="rounded-xl border border-zinc-200 px-3.5 py-1.5 text-xs font-semibold hover:border-zinc-400 dark:border-zinc-700"
                  >
                    {isSelected ? "Close Assignment" : "Assign Staff"}
                  </button>
                </div>

                {/* Staff Assignment Drawer */}
                {isSelected && (
                  <div className="rounded-2xl bg-zinc-50 p-4 dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 space-y-3 mt-3">
                    <h4 className="text-xs font-bold uppercase text-zinc-500">Assign Driver & Mechanic</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <label className="block text-xs font-semibold">
                        Assign Valet / Driver
                        <select
                          className="mt-1 w-full rounded-xl border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-800"
                          value={driverId}
                          onChange={(e) => setDriverId(e.target.value)}
                        >
                          <option value="">Select Driver...</option>
                          {employees?.drivers?.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.name} ({d.phone || d.email})
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="block text-xs font-semibold">
                        Assign Mechanic
                        <select
                          className="mt-1 w-full rounded-xl border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-800"
                          value={mechanicId}
                          onChange={(e) => setMechanicId(e.target.value)}
                        >
                          <option value="">Select Mechanic...</option>
                          {employees?.mechanics?.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name} ({m.phone || m.email})
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <button
                      disabled={updating}
                      onClick={() => handleAssignAndStatus(b)}
                      className="w-full rounded-xl bg-[#ff4d2e] py-2 text-xs font-bold text-white hover:bg-[#e03e21]"
                    >
                      {updating ? "Saving Assignments..." : "Save Staff Assignments"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
