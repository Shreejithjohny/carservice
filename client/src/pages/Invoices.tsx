import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { Skeleton, Empty } from "../components/States";
import { Receipt, Printer, X, Wallet, FileDown } from "lucide-react";
import { downloadFile } from "../services/api";
import { useToast } from "../hooks/useToast";
import { useAuth } from "../hooks/useAuth";
import { PaymentModal } from "../components/PaymentModal";
import type { Invoice } from "../types";

const STATUS_STYLES: Record<string, string> = {
  PAID: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  FAILED: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
};

export function Invoices() {
  const { user } = useAuth();
  const { data: invoices, loading, reload } = useApi<Invoice[]>("/api/invoices/");
  const { data: health } = useApi<{ payment_gateway?: string | null }>("/api/health-check/");
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [payingInvoice, setPayingInvoice] = useState<Invoice | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("ALL");
  const [downloading, setDownloading] = useState(false);
  const { push } = useToast();

  async function downloadPdf(inv: Invoice) {
    setDownloading(true);
    try {
      await downloadFile(`/api/invoices/${inv.id}/pdf/`, `${inv.invoice_number}.pdf`);
    } catch (err) {
      push({ title: err instanceof Error ? err.message : "Could not download the invoice", tone: "err" });
    } finally {
      setDownloading(false);
    }
  }

  if (loading && !invoices) return <Skeleton className="h-80" />;

  const gateway = health?.payment_gateway || "";
  const canPay = (inv: Invoice) =>
    !!gateway &&
    user?.role.toLowerCase() === "customer" &&
    String(inv.customer) === String(user.id) &&
    inv.payment_status !== "PAID" &&
    inv.invoice_status !== "CANCELLED";

  // "PENDING" means unpaid, which includes invoices whose last payment attempt failed
  const filtered = (invoices || []).filter((inv) => {
    if (filterStatus === "ALL") return true;
    if (filterStatus === "PENDING") return inv.payment_status !== "PAID";
    return inv.payment_status === filterStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold flex items-center gap-2">
            <Receipt className="text-[#ff4d2e]" /> Service Invoices
          </h1>
          <p className="text-sm text-zinc-500">View and download your official itemized service bills.</p>
        </div>

        <div className="flex items-center gap-2">
          {["ALL", "PENDING", "PAID"].map((st) => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                filterStatus === st
                  ? "bg-[#ff4d2e] text-white"
                  : "border border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {!filtered.length ? (
        <Empty title="No invoices found" hint="Invoices appear here once your vehicle service is completed." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((inv) => (
            <div
              key={inv.id}
              onClick={() => setSelectedInvoice(inv)}
              className="glass cursor-pointer rounded-3xl p-5 transition hover:scale-[1.01] hover:shadow-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-mono font-bold text-[#ff4d2e]">{inv.invoice_number}</span>
                  <h3 className="text-base font-bold mt-1">
                    {inv.vehicle_details ? `${inv.vehicle_details.brand} ${inv.vehicle_details.model}` : "Vehicle Service"}
                  </h3>
                  <p className="text-xs text-zinc-500">{inv.booking_reference}</p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
                    STATUS_STYLES[inv.payment_status] || "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {inv.payment_status}
                </span>
              </div>

              <div className="mt-4 flex items-baseline justify-between border-t border-zinc-200/60 pt-3 dark:border-zinc-800">
                <span className="text-xs text-zinc-500">Grand Total</span>
                <span className="text-xl font-black">₹{Number(inv.grand_total).toLocaleString("en-IN")}</span>
              </div>

              {canPay(inv) && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPayingInvoice(inv);
                  }}
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#ff4d2e] py-2.5 text-sm font-bold text-white hover:bg-[#e94529]"
                >
                  <Wallet size={16} /> {inv.payment_status === "FAILED" ? "Retry payment" : "Pay now"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Printable Invoice Modal */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="relative max-h-[95vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white p-8 text-zinc-900 shadow-2xl dark:bg-zinc-900 dark:text-white print:m-0 print:p-0">
            <div className="flex items-center justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800 print:hidden">
              <span className="text-xs font-bold uppercase tracking-widest text-[#ff4d2e]">Service Invoice</span>
              <div className="flex items-center gap-2">
                {canPay(selectedInvoice) && (
                  <button
                    onClick={() => setPayingInvoice(selectedInvoice)}
                    className="flex items-center gap-1.5 rounded-xl bg-[#ff4d2e] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#e94529]"
                  >
                    <Wallet className="h-3.5 w-3.5" /> Pay now
                  </button>
                )}
                <button
                  onClick={() => downloadPdf(selectedInvoice)}
                  disabled={downloading}
                  className="flex items-center gap-1.5 rounded-xl bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
                >
                  <FileDown className="h-3.5 w-3.5" /> {downloading ? "Preparing..." : "Download PDF"}
                </button>
                <button
                  onClick={() => window.print()}
                  className="flex items-center gap-1.5 rounded-xl bg-zinc-100 px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
                >
                  <Printer className="h-3.5 w-3.5" /> Print
                </button>
                <button
                  onClick={() => setSelectedInvoice(null)}
                  className="rounded-full p-1.5 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Printable Content */}
            <div className="space-y-6 pt-4">
              <div className="flex justify-between">
                <div>
                  <h2 className="text-2xl font-black text-[#ff4d2e]">SMART DOORSTEP</h2>
                  <p className="text-xs text-zinc-500">Vehicle Service & Maintenance Platform</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm font-bold">{selectedInvoice.invoice_number}</p>
                  <p className="text-xs text-zinc-500">
                    Date: {new Date(selectedInvoice.issued_at || selectedInvoice.created_at || "").toLocaleDateString()}
                  </p>
                </div>
              </div>

              {/* Bill Details */}
              <div className="grid grid-cols-2 gap-4 rounded-2xl bg-zinc-50 p-4 text-xs dark:bg-zinc-800/50">
                <div>
                  <p className="font-bold text-zinc-500 uppercase tracking-wider mb-1">Customer & Vehicle</p>
                  <p className="font-semibold">{selectedInvoice.customer_name || selectedInvoice.customer_email}</p>
                  <p className="text-zinc-500">{selectedInvoice.customer_phone}</p>
                  <p className="mt-1 font-semibold">
                    {selectedInvoice.vehicle_details?.brand} {selectedInvoice.vehicle_details?.model}
                  </p>
                  <p className="text-zinc-500">Reg: {selectedInvoice.vehicle_details?.registration_number}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-zinc-500 uppercase tracking-wider mb-1">Service Provider</p>
                  <p className="font-semibold">{selectedInvoice.service_center_name || "Smart Doorstep Hub"}</p>
                  <p className="text-zinc-500">Booking: {selectedInvoice.booking_reference}</p>
                  <p className="mt-2 font-bold uppercase text-[#ff4d2e]">Status: {selectedInvoice.payment_status}</p>
                </div>
              </div>

              {/* Items Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800">
                      <th className="py-2">Description</th>
                      <th className="py-2">Type</th>
                      <th className="py-2 text-center">Qty</th>
                      <th className="py-2 text-right">Unit Price</th>
                      <th className="py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60">
                    {(selectedInvoice.items || []).map((item, idx) => (
                      <tr key={idx}>
                        <td className="py-2.5 font-medium">{item.description}</td>
                        <td className="py-2.5 text-zinc-500">{item.item_type}</td>
                        <td className="py-2.5 text-center">{item.quantity}</td>
                        <td className="py-2.5 text-right font-mono">₹{Number(item.unit_price).toFixed(2)}</td>
                        <td className="py-2.5 text-right font-mono font-bold">₹{Number(item.total_price).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Financial Totals */}
              <div className="space-y-1.5 border-t border-zinc-200 pt-3 text-xs dark:border-zinc-800">
                <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                  <span>Base Service Charge:</span>
                  <span className="font-mono">₹{Number(selectedInvoice.subtotal).toFixed(2)}</span>
                </div>
                {Number(selectedInvoice.additional_repairs_total) > 0 && (
                  <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                    <span>Approved Extra Repairs:</span>
                    <span className="font-mono">₹{Number(selectedInvoice.additional_repairs_total).toFixed(2)}</span>
                  </div>
                )}
                {Number(selectedInvoice.labor_total) > 0 && (
                  <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                    <span>Specialized Labor:</span>
                    <span className="font-mono">₹{Number(selectedInvoice.labor_total).toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                  <span>GST (18%):</span>
                  <span className="font-mono">₹{Number(selectedInvoice.tax).toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-zinc-200 pt-2 text-base font-black text-zinc-900 dark:border-zinc-800 dark:text-white">
                  <span>Grand Total:</span>
                  <span className="font-mono text-[#ff4d2e]">₹{Number(selectedInvoice.grand_total).toLocaleString("en-IN")}</span>
                </div>
              </div>

              {selectedInvoice.payments?.some((p) => p.status === "SUCCESS") && (
                <div className="rounded-2xl bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300">
                  {selectedInvoice.payments
                    .filter((p) => p.status === "SUCCESS")
                    .map((p) => (
                      <p key={p.id}>
                        <strong>Paid ₹{Number(p.amount).toLocaleString("en-IN")}</strong> via {p.method === "UPI" ? `UPI (${p.payer_reference})` : p.payer_reference} on{" "}
                        {new Date(p.created_at).toLocaleString()} · Transaction <span className="font-mono">{p.transaction_id}</span>
                        {p.provider === "MOCK" && " (test payment)"}
                      </p>
                    ))}
                </div>
              )}

              <div className="rounded-xl border border-zinc-200/80 bg-zinc-50 p-3 text-center text-[11px] text-zinc-500 dark:border-zinc-800 dark:bg-zinc-800/40">
                This is an electronically generated service invoice. Thank you for choosing Smart Doorstep Vehicle Service.
              </div>
            </div>
          </div>
        </div>
      )}

      {payingInvoice && (
        <PaymentModal
          invoice={payingInvoice}
          gateway={gateway}
          onClose={() => {
            setPayingInvoice(null);
            reload();
          }}
          onPaid={(updated) => {
            setPayingInvoice(null);
            if (selectedInvoice?.id === updated.id) setSelectedInvoice(updated);
            reload();
          }}
        />
      )}
    </div>
  );
}
