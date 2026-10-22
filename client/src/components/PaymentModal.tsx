import { FormEvent, useState } from "react";
import { CreditCard, Smartphone, X } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { Invoice, Payment } from "../types";

type PayResponse = { payment: Payment; invoice: Invoice };

export function PaymentModal({
  invoice,
  gateway,
  onClose,
  onPaid,
}: {
  invoice: Invoice;
  gateway: string;
  onClose: () => void;
  onPaid: (invoice: Invoice, payment: Payment) => void;
}) {
  const { push } = useToast();
  const [method, setMethod] = useState<"UPI" | "CARD">("UPI");
  const [upiId, setUpiId] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const amount = Number(invoice.grand_total).toLocaleString("en-IN", { minimumFractionDigits: 2 });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = method === "UPI" ? { method, upi_id: upiId } : { method, card_number: cardNumber, card_expiry: cardExpiry };
      const res = await api<PayResponse>(`/api/invoices/${invoice.id}/pay/`, { method: "POST", body: JSON.stringify(body) });
      push({ title: `Payment successful · ${res.payment.transaction_id}` });
      onPaid(res.invoice, res.payment);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Payment failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]";

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <form onSubmit={onSubmit} className="relative w-full max-w-md space-y-4 rounded-3xl bg-white p-6 text-zinc-900 shadow-2xl dark:bg-zinc-900 dark:text-white">
        <button type="button" onClick={onClose} className="absolute right-4 top-4 rounded-full p-1.5 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800" aria-label="Close">
          <X className="h-5 w-5" />
        </button>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[#ff4d2e]">Pay invoice</p>
          <h2 className="mt-1 text-2xl font-black">₹{amount}</h2>
          <p className="text-xs text-zinc-500">{invoice.invoice_number}</p>
        </div>

        {gateway === "mock" && (
          <div className="rounded-2xl border border-amber-300/60 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
            <strong>Test mode — no real money is charged.</strong> Any valid UPI ID or card number (e.g. 4111 1111 1111 1111) succeeds.
            Use <code>failure@mock</code> or card <code>4000 0000 0000 0002</code> to see a declined payment.
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          {(["UPI", "CARD"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMethod(m)}
              className={`flex items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-bold transition ${
                method === m ? "bg-[#ff4d2e] text-white" : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              }`}
            >
              {m === "UPI" ? <Smartphone size={16} /> : <CreditCard size={16} />} {m === "UPI" ? "UPI" : "Card"}
            </button>
          ))}
        </div>

        {method === "UPI" ? (
          <label className="block text-xs font-semibold text-zinc-500">
            UPI ID
            <input required className={input} placeholder="name@okbank" value={upiId} onChange={(e) => setUpiId(e.target.value)} autoComplete="off" />
          </label>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            <label className="col-span-2 block text-xs font-semibold text-zinc-500">
              Card number
              <input
                required
                inputMode="numeric"
                className={input}
                placeholder="4111 1111 1111 1111"
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                autoComplete="cc-number"
              />
            </label>
            <label className="block text-xs font-semibold text-zinc-500">
              Expiry
              <input required className={input} placeholder="MM/YY" value={cardExpiry} onChange={(e) => setCardExpiry(e.target.value)} autoComplete="cc-exp" />
            </label>
          </div>
        )}

        {error && <p className="rounded-2xl bg-rose-500/10 p-3 text-xs font-semibold text-rose-600 dark:text-rose-400">{error}</p>}

        <button disabled={busy} type="submit" className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-bold text-white disabled:opacity-50">
          {busy ? "Processing..." : `Pay ₹${amount}`}
        </button>
      </form>
    </div>
  );
}
