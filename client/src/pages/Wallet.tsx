import { useAuth } from "../hooks/useAuth";
import { useApi } from "../hooks/useApi";
import { Empty, Skeleton } from "../components/States";

type Discount = { _id: string; title: string; percent: number; code: string };

export function Wallet() {
  const { user } = useAuth();
  const discounts = useApi<Discount[]>("/api/discounts");
  if (discounts.loading) return <Skeleton className="h-40" />;
  return (
    <div className="space-y-4">
      <div className="rounded-3xl bg-gradient-to-br from-[#ff4d2e] to-orange-400 p-6 text-white">
        <p className="text-xs uppercase tracking-widest">Wallet</p>
        <p className="text-4xl font-extrabold">₹{(user?.walletBalance ?? 0).toLocaleString("en-IN")}</p>
      </div>
      <h2 className="font-bold">Offers</h2>
      {discounts.error && <Empty title="Offers unavailable" />}
      {discounts.data?.map((d) => (
        <div key={d._id} className="glass flex items-center justify-between rounded-3xl p-5">
          <div>
            <p className="font-bold">{d.title}</p>
            <p className="text-sm text-zinc-500">{d.percent}% off</p>
          </div>
          <code className="rounded-full bg-zinc-900 px-3 py-1 text-xs text-white dark:bg-white dark:text-zinc-900">{d.code}</code>
        </div>
      ))}
    </div>
  );
}

export function Offers() {
  return <Wallet />;
}
