import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import { CostModelPanel } from "../components/CostModelPanel";
import type { Booking, AdminStats } from "../types";
import { BRAND } from "../utils/theme";

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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Stat label="Total Customers" value={stats.total_customers} />
        <Stat label="Total Vehicles" value={stats.total_vehicles} />
        <Stat label="Active Services" value={stats.active_services} />
        <Stat label="Completed Services" value={stats.completed_services} />
        <Stat label="Service Centers" value={stats.service_centers} />
        <Stat label="Valets / Drivers" value={stats.total_drivers} />
        <Stat label="Service Mechanics" value={stats.total_mechanics} />
        <Stat label="Revenue Collected (paid invoices)" value={`₹${stats.total_revenue.toLocaleString("en-IN")}`} />
        <Stat label="Outstanding (unpaid invoices)" value={`₹${stats.outstanding_amount.toLocaleString("en-IN")}`} />
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
            <Bar dataKey="v" fill={BRAND} radius={8} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <CostModelPanel />

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
                  <span className="font-mono font-bold text-brand-fg mr-2">{b.booking_reference}</span>
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
