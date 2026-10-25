import { useParams, Link } from "react-router-dom";
import { ShieldCheck, ShieldX } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { Skeleton } from "../components/States";

interface Verification {
  valid: boolean;
  invoice_number: string;
  issued_at: string;
  service_center: string | null;
  vehicle: string;
  grand_total: string;
  payment_status: string;
  invoice_status: string;
}

/** Public page opened by scanning the QR code printed on an invoice PDF. */
export function VerifyInvoice() {
  const { token = "" } = useParams();
  const { data, error, loading } = useApi<Verification>(`/api/invoices/verify/${encodeURIComponent(token)}/`);

  return (
    <div className="min-h-dvh bg-[#f6f3ee] px-4 py-12 text-zinc-900 dark:bg-[#07080c] dark:text-zinc-100">
      <div className="glass mx-auto max-w-md rounded-3xl p-8 space-y-5">
        <p className="text-center text-xl font-extrabold">
          Door<span className="text-[#ff4d2e]">Step</span> invoice check
        </p>
        {loading ? (
          <Skeleton className="h-40" />
        ) : error || !data?.valid ? (
          <div className="space-y-2 text-center">
            <ShieldX size={56} className="mx-auto text-red-500" />
            <h1 className="text-xl font-bold">Not a valid DoorStep invoice</h1>
            <p className="text-sm text-zinc-500">This code does not match any invoice we issued. The document may have been altered.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2 text-center">
              <ShieldCheck size={56} className="mx-auto text-emerald-500" />
              <h1 className="text-xl font-bold">Genuine invoice</h1>
            </div>
            <dl className="divide-y divide-zinc-200 rounded-2xl border border-zinc-200 text-sm dark:divide-zinc-800 dark:border-zinc-800">
              {[
                ["Invoice", data.invoice_number],
                ["Issued", new Date(data.issued_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })],
                ["Service center", data.service_center || "—"],
                ["Vehicle", data.vehicle],
                ["Amount", `₹${Number(data.grand_total).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`],
                ["Payment", data.payment_status === "PAID" ? "Paid" : "Not paid yet"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 px-4 py-2.5">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className={`font-semibold text-right ${k === "Payment" && data.payment_status !== "PAID" ? "text-amber-600" : ""}`}>{v}</dd>
                </div>
              ))}
            </dl>
            {data.invoice_status === "CANCELLED" && (
              <p className="rounded-xl bg-red-50 p-3 text-center text-sm font-semibold text-red-600 dark:bg-red-950/30">This invoice has been cancelled.</p>
            )}
          </div>
        )}
        <Link to="/" className="block text-center text-sm font-semibold text-[#ff4d2e]">
          Go to DoorStep
        </Link>
      </div>
    </div>
  );
}
