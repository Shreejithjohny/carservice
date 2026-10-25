import { useState } from "react";
import { Star } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { useLanguage } from "../hooks/useLanguage";

function Stars({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-semibold text-zinc-500">{label}</span>
      <div className="flex gap-0.5" role="radiogroup" aria-label={label}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? "s" : ""}`} onClick={() => onChange(n)}>
            <Star size={22} className={n <= value ? "fill-amber-400 text-amber-400" : "text-zinc-300 dark:text-zinc-600"} />
          </button>
        ))}
      </div>
    </div>
  );
}

/** Rate a completed booking: the service center, and the driver when one did the pickup. */
export function ReviewForm({ bookingId, hasDriver, onDone }: { bookingId: string | number; hasDriver: boolean; onDone: () => void }) {
  const { push } = useToast();
  const { t } = useLanguage();
  const [center, setCenter] = useState(0);
  const [driver, setDriver] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!center) return push({ title: t("review.rateCenter"), tone: "err" });
    setBusy(true);
    try {
      await api(`/api/bookings/${bookingId}/review/`, {
        method: "POST",
        body: JSON.stringify({ center_rating: center, ...(hasDriver && driver ? { driver_rating: driver } : {}), comment }),
      });
      push({ title: t("review.thanks") });
      onDone();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not save your review", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/60 p-4 dark:border-amber-900/40 dark:bg-amber-950/20">
      <p className="text-sm font-bold">{t("review.title")}</p>
      <Stars label={t("review.center")} value={center} onChange={setCenter} />
      {hasDriver && <Stars label={t("review.driver")} value={driver} onChange={setDriver} />}
      <textarea
        rows={2}
        maxLength={1000}
        className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        placeholder={t("review.placeholder")}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <button
        type="button"
        disabled={busy}
        onClick={submit}
        className="w-full rounded-xl bg-brand py-2 text-sm font-bold text-white disabled:opacity-50"
      >
        {busy ? t("review.saving") : t("review.submit")}
      </button>
    </div>
  );
}
