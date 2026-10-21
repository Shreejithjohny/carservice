import { FormEvent, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { Booking, AdminStats } from "../types";

export function AdminHome() {
  const { data: stats, loading, error, reload } = useApi<AdminStats>("/api/admin/dashboard-stats/");
  const { data: bookings } = useApi<Booking[]>("/api/bookings/");

  if (loading) return <Skeleton className="h-64" />;
  if (error || !stats) return <Empty title="Admin analytics unavailable" hint={error || "Could not load stats"} />;

  const chart = [
    { name: "Customers", v: stats.total_customers },
    { name: "Vehicles", v: stats.total_vehicles },
    { name: "Bookings", v: stats.total_bookings },
    { name: "Active", v: stats.active_services },
    { name: "Completed", v: stats.completed_services },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black">Platform Administration</h1>
          <p className="text-sm text-zinc-500">Live operational and financial metrics</p>
        </div>
        <button
          onClick={reload}
          className="rounded-xl border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
        >
          Refresh Data
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total Customers" value={stats.total_customers} />
        <Stat label="Total Vehicles" value={stats.total_vehicles} />
        <Stat label="Active Services" value={stats.active_services} />
        <Stat label="Completed Services" value={stats.completed_services} />
        <Stat label="Service Centers" value={stats.service_centers} />
        <Stat label="Valets / Drivers" value={stats.total_drivers} />
        <Stat label="Service Mechanics" value={stats.total_mechanics} />
        <Stat label="Total Platform Revenue" value={`₹${stats.total_revenue.toLocaleString("en-IN")}`} />
      </div>

      {/* Repair Approval Breakdown */}
      <div className="glass rounded-3xl p-5">
        <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-500 mb-3">
          Additional Repair Requests Breakdown
        </h3>
        <div className="grid grid-cols-4 gap-3 text-center">
          <div className="rounded-2xl bg-zinc-50 p-3 dark:bg-zinc-800/60">
            <p className="text-xs text-zinc-400">Total Requested</p>
            <p className="text-xl font-bold mt-1">{stats.repair_approvals.total}</p>
          </div>
          <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-600 dark:text-emerald-400">
            <p className="text-xs font-bold uppercase">Approved</p>
            <p className="text-xl font-bold mt-1">{stats.repair_approvals.approved}</p>
          </div>
          <div className="rounded-2xl bg-amber-500/10 p-3 text-amber-600 dark:text-amber-400">
            <p className="text-xs font-bold uppercase">Pending</p>
            <p className="text-xl font-bold mt-1">{stats.repair_approvals.pending}</p>
          </div>
          <div className="rounded-2xl bg-rose-500/10 p-3 text-rose-600 dark:text-rose-400">
            <p className="text-xs font-bold uppercase">Rejected</p>
            <p className="text-xl font-bold mt-1">{stats.repair_approvals.rejected}</p>
          </div>
        </div>
      </div>

      <div className="glass h-64 rounded-3xl p-4">
        <p className="text-xs font-bold uppercase tracking-wider text-zinc-400 mb-2">Volume Distribution</p>
        <ResponsiveContainer width="100%" height="85%">
          <BarChart data={chart}>
            <XAxis dataKey="name" stroke="#888888" fontSize={12} />
            <Tooltip />
            <Bar dataKey="v" fill="#ff4d2e" radius={8} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent bookings list */}
      <section className="glass rounded-3xl p-5">
        <h3 className="font-bold mb-3">Live Service Bookings</h3>
        {!bookings?.length ? (
          <p className="text-xs text-zinc-500">No active bookings</p>
        ) : (
          <div className="divide-y divide-zinc-200/60 dark:divide-zinc-800">
            {bookings.slice(0, 5).map((b) => (
              <div key={b.id} className="py-2.5 flex items-center justify-between text-xs">
                <div>
                  <span className="font-mono font-bold text-[#ff4d2e] mr-2">{b.booking_reference}</span>
                  <span className="font-medium">{b.service_type_details?.name || "Service"}</span>
                </div>
                <span className="rounded-full bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 font-semibold">
                  {b.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="glass rounded-3xl p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-2xl font-extrabold">{value}</p>
    </div>
  );
}

export function AdminBookings() {
  const { data, loading, reload } = useApi<Booking[]>("/api/bookings");
  const { push } = useToast();
  if (loading) return <Skeleton className="h-40" />;
  if (!data?.length) return <Empty title="No bookings" />;
  return (
    <div className="space-y-3">
      {data.map((b) => (
        <div key={b._id} className="glass flex flex-wrap items-center justify-between gap-2 rounded-3xl p-4">
          <div>
            <p className="font-bold">{b.serviceType}</p>
            <p className="text-sm text-zinc-500">{b.status}</p>
          </div>
          <select
            className="rounded-2xl border border-zinc-200 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={b.status}
            onChange={async (e) => {
              await api(`/api/bookings/${b._id}/status`, { method: "PATCH", body: JSON.stringify({ status: e.target.value }) });
              push({ title: "Status updated" });
              reload();
            }}
          >
            {["Requested", "Driver Assigned", "OTP Verified", "Vehicle Picked Up", "In Service", "Waiting for Approval", "Repair Started", "Completed", "Out for Delivery", "Delivered"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

export function AdminVideo() {
  const bookings = useApi<Booking[]>("/api/bookings");
  const { push } = useToast();
  const [bookingId, setBookingId] = useState("");
  const [title, setTitle] = useState("Front brake pad replacement");
  const [description, setDescription] = useState("Pads worn below safe limit.");
  const [extraCost, setExtraCost] = useState(4200);
  const [extraHours, setExtraHours] = useState(3);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const id = bookingId || bookings.data?.[0]?._id;
    if (!id) return;
    await api("/api/approvals", {
      method: "POST",
      body: JSON.stringify({ bookingId: id, title, description, extraCost, extraHours }),
    });
    push({ title: "Video approval sent to customer" });
  }

  return (
    <form className="glass max-w-xl space-y-3 rounded-3xl p-6" onSubmit={onSubmit}>
      <select className="w-full rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={bookingId} onChange={(e) => setBookingId(e.target.value)}>
        {bookings.data?.map((b) => <option key={b._id} value={b._id}>{b.serviceType} · {b.status}</option>)}
      </select>
      <input className="w-full rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className="w-full rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={description} onChange={(e) => setDescription(e.target.value)} />
      <input type="number" className="w-full rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={extraCost} onChange={(e) => setExtraCost(Number(e.target.value))} />
      <input type="number" className="w-full rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={extraHours} onChange={(e) => setExtraHours(Number(e.target.value))} />
      <button className="rounded-2xl bg-[#ff4d2e] px-4 py-2 font-semibold text-white" type="submit">Upload repair video</button>
    </form>
  );
}

export function AdminDiscounts() {
  const { data, reload } = useApi<{ _id: string; title: string; percent: number; code: string }[]>("/api/discounts");
  const { push } = useToast();
  const [title, setTitle] = useState("Weekend 15");
  const [percent, setPercent] = useState(15);
  const [code, setCode] = useState("WEEK15");
  return (
    <div className="space-y-4">
      <form
        className="glass flex flex-wrap gap-2 rounded-3xl p-4"
        onSubmit={async (e) => {
          e.preventDefault();
          await api("/api/discounts", { method: "POST", body: JSON.stringify({ title, percent, code }) });
          push({ title: "Discount saved" });
          reload();
        }}
      >
        <input className="rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input type="number" className="w-24 rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={percent} onChange={(e) => setPercent(Number(e.target.value))} />
        <input className="rounded-2xl border px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" value={code} onChange={(e) => setCode(e.target.value)} />
        <button className="rounded-2xl bg-[#ff4d2e] px-4 py-2 text-white" type="submit">Add</button>
      </form>
      {data?.map((d) => (
        <div key={d._id} className="glass flex justify-between rounded-3xl p-4">
          <span>{d.title}</span>
          <span>{d.percent}% · {d.code}</span>
        </div>
      ))}
    </div>
  );
}
