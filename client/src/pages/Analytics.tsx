import { useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Star } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { Empty, Skeleton } from "../components/States";
import type { CenterAnalytics, ServiceCenter } from "../types";
import { BRAND } from "../utils/theme";

// Every chart here shows a single series, so it uses the one brand accent (validated >= 3:1 on both themes).
const ACCENT = BRAND;
const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="glass rounded-2xl p-4">
      <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-black">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}

function ChartTooltip({ active, payload, label, format }: { active?: boolean; payload?: { value: number }[]; label?: string; format: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
      <p className="font-semibold text-zinc-500">{label}</p>
      <p className="font-bold">{format(payload[0].value)}</p>
    </div>
  );
}

/** One titled single-series bar chart, with its numbers also available as a table. */
type Row = Record<string, string | number>;

function ChartCard({
  title,
  rows,
  xKey,
  yKey,
  format,
  horizontal = false,
}: {
  title: string;
  rows: Row[];
  xKey: string;
  yKey: string;
  format: (v: number) => string;
  horizontal?: boolean;
}) {
  const height = horizontal ? Math.max(160, rows.length * 40) : 240;
  return (
    <section className="glass rounded-3xl p-5 space-y-3">
      <h2 className="text-sm font-bold">{title}</h2>
      {rows.every((r) => !Number(r[yKey])) ? (
        <p className="flex items-center justify-center rounded-2xl bg-zinc-100/70 text-sm text-zinc-500 dark:bg-zinc-800/50" style={{ height }}>
          Nothing recorded in this period yet.
        </p>
      ) : (
        <div className="text-zinc-500" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            {horizontal ? (
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} stroke="currentColor" strokeOpacity={0.15} />
                <XAxis type="number" allowDecimals={false} tick={{ fill: "currentColor", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey={xKey} width={130} tick={{ fill: "currentColor", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "currentColor", fillOpacity: 0.06 }} content={<ChartTooltip format={format} />} />
                <Bar dataKey={yKey} fill={ACCENT} radius={[0, 4, 4, 0]} maxBarSize={22} />
              </BarChart>
            ) : (
              <BarChart data={rows} margin={{ left: 0, right: 8 }}>
                <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.15} />
                <XAxis dataKey={xKey} tick={{ fill: "currentColor", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  allowDecimals={false}
                  width={64}
                  tickFormatter={(v: number) => (yKey === "revenue" ? (v >= 1000 ? `₹${Math.round(v / 1000)}k` : `₹${v}`) : String(v))}
                  tick={{ fill: "currentColor", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: "currentColor", fillOpacity: 0.06 }} content={<ChartTooltip format={format} />} />
                <Bar dataKey={yKey} fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
      <details className="text-xs">
        <summary className="cursor-pointer font-semibold text-zinc-500">Show as table</summary>
        <table className="mt-2 w-full">
          <tbody>
            {rows.map((r) => (
              <tr key={String(r[xKey])} className="border-t border-zinc-200/70 dark:border-zinc-800">
                <td className="py-1">{String(r[xKey])}</td>
                <td className="py-1 text-right font-semibold">{format(Number(r[yKey]))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function hours(h: number | null) {
  if (h == null) return "—";
  return h >= 48 ? `${(h / 24).toFixed(1)} days` : `${h} h`;
}

export function Analytics() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [centerId, setCenterId] = useState("");
  const [months, setMonths] = useState(6);
  const { data: centers } = useApi<ServiceCenter[]>(isAdmin ? "/api/service-centers/" : null);
  const { data, loading, error } = useApi<CenterAnalytics>(
    `/api/service-center/analytics/?months=${months}${centerId ? `&center=${centerId}` : ""}`
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold">
            <BarChart3 className="text-brand-fg" /> Analytics
          </h1>
          <p className="text-sm text-zinc-500">{data?.scope ?? "Loading..."}</p>
        </div>
        <div className="flex gap-2">
          {isAdmin && (
            <select
              className="rounded-xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={centerId}
              onChange={(e) => setCenterId(e.target.value)}
            >
              <option value="">All centers</option>
              {centers?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          <select
            className="rounded-xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
          >
            {[3, 6, 12].map((m) => (
              <option key={m} value={m}>
                Last {m} months
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && !data ? (
        <Skeleton className="h-96" />
      ) : error || !data ? (
        <Empty title="Analytics unavailable" hint={error ?? undefined} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile label="Bookings" value={data.totals.bookings} hint={`${data.totals.completed} completed · ${data.totals.cancelled} cancelled`} />
            <Tile label="Revenue collected" value={inr(data.totals.revenue_paid)} hint={`${inr(data.totals.outstanding)} still unpaid`} />
            <Tile
              label="Typical turnaround"
              value={hours(data.turnaround_hours.median)}
              hint={data.turnaround_hours.count ? `median of ${data.turnaround_hours.count} jobs, booking → car returned` : "no completed jobs yet"}
            />
            <Tile
              label="Customer rating"
              value={
                data.ratings.average != null ? (
                  <span className="flex items-center gap-1">
                    {data.ratings.average} <Star size={18} className="fill-amber-400 text-amber-400" />
                  </span>
                ) : (
                  "—"
                )
              }
              hint={`${data.ratings.count} review${data.ratings.count === 1 ? "" : "s"}`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Revenue collected per month (paid invoices)" rows={data.monthly} xKey="label" yKey="revenue" format={inr} />
            <ChartCard title="New bookings per month" rows={data.monthly} xKey="label" yKey="bookings" format={(v) => `${v} bookings`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {data.repairs.top.length ? (
              <ChartCard
                title="Most requested extra repairs"
                rows={data.repairs.top}
                xKey="title"
                yKey="count"
                format={(v) => `${v} request${v === 1 ? "" : "s"}`}
                horizontal
              />
            ) : (
              <Empty title="No extra repairs requested yet" />
            )}
            <section className="glass rounded-3xl p-5 space-y-3">
              <h2 className="text-sm font-bold">Repair approvals</h2>
              <p className="text-4xl font-black">{data.repairs.approval_rate != null ? `${data.repairs.approval_rate}%` : "—"}</p>
              <p className="text-xs text-zinc-500">
                of answered repair requests approved by customers ({data.repairs.approved} approved, {data.repairs.rejected} declined,{" "}
                {data.repairs.pending} waiting)
              </p>
              <h3 className="pt-3 text-sm font-bold">Recent comments</h3>
              {data.ratings.recent.length ? (
                <ul className="space-y-2 text-sm">
                  {data.ratings.recent.map((r, i) => (
                    <li key={i} className="rounded-xl bg-zinc-100/70 p-3 dark:bg-zinc-800/60">
                      <span className="font-bold text-amber-600">{"★".repeat(r.rating)}</span> {r.comment}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">No written reviews yet.</p>
              )}
            </section>
          </div>

          <ChartCard
            title="Bookings by current status"
            rows={data.status_breakdown}
            xKey="status"
            yKey="count"
            format={(v) => `${v} booking${v === 1 ? "" : "s"}`}
            horizontal
          />
        </>
      )}
    </div>
  );
}
