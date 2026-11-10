import { FormEvent, useState } from "react";
import { X } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { useLanguage } from "../hooks/useLanguage";
import { Skeleton } from "./States";
import type { Booking } from "../types";

type Slot = { time: string; label: string; available: number; capacity: number; is_full: boolean };

function isoDay(offsetDays: number) {
  const d = new Date(Date.now() + offsetDays * 24 * 60 * 60 * 1000);
  // Local calendar date, not UTC (toISOString would give yesterday early in the morning in India)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Lets the customer move a pickup to another date or time slot that still has room. */
export function RescheduleDialog({ booking, onClose, onDone }: Readonly<{ booking: Booking; onClose: () => void; onDone: () => void }>) {
  const { push } = useToast();
  const { t } = useLanguage();
  const centerId = booking.service_center ?? booking.service_center_details?.id;
  const [day, setDay] = useState(booking.preferred_date || isoDay(1));
  const [time, setTime] = useState("");
  const [busy, setBusy] = useState(false);
  const { data, loading } = useApi<{ slots: Slot[] }>(centerId && day ? `/api/service-centers/${centerId}/slots/?date=${day}` : null);
  const slots = data?.slots ?? [];
  const isCurrent = (slot: Slot) => day === booking.preferred_date && slot.time === booking.preferred_time;
  const chosen = slots.find((s) => s.time === time && !s.is_full && !isCurrent(s));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!chosen) return push({ title: t("book.pickSlot"), tone: "err" });
    setBusy(true);
    try {
      await api(`/api/bookings/${booking.id}/`, { method: "PATCH", body: JSON.stringify({ preferred_date: day, preferred_time: chosen.time }) });
      push({ title: t("track.rescheduled", { when: `${day}, ${chosen.label}` }) });
      onDone();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not reschedule", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      open
      aria-labelledby="reschedule-title"
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center bg-black/60 p-4 text-inherit backdrop-blur-sm"
    >
      <form className="glass w-full max-w-md space-y-4 rounded-3xl bg-white p-6 dark:bg-zinc-900" onSubmit={onSubmit}>
        <div className="flex items-center justify-between">
          <h2 id="reschedule-title" className="text-lg font-extrabold">{t("track.reschedule")}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-1 text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800">
            <X size={18} />
          </button>
        </div>
        <label className="block text-xs font-semibold text-zinc-500">
          {t("book.date")}
          <input
            type="date"
            required
            className="mt-1 w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={day}
            min={isoDay(0)}
            max={isoDay(30)}
            onChange={(e) => {
              setDay(e.target.value);
              setTime("");
            }}
          />
        </label>
        <div className="text-xs font-semibold text-zinc-500">
          <span className="mb-1.5 block">{t("book.slot")}</span>
          {loading ? (
            <Skeleton className="h-20" />
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {slots.map((s) => {
                const current = isCurrent(s);
                return (
                  <button
                    key={s.time}
                    type="button"
                    disabled={s.is_full || current}
                    onClick={() => setTime(s.time)}
                    className={`rounded-2xl border px-3 py-2.5 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${
                      chosen?.time === s.time ? "border-brand bg-brand/10 text-brand-fg" : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700"
                    }`}
                  >
                    <span className="block text-sm font-bold">{s.label}</span>
                    <span className={`text-[11px] ${current ? "text-zinc-500" : s.is_full ? "text-red-500" : "text-emerald-600"}`}>
                      {current ? t("track.currentSlot") : s.is_full ? t("book.full") : t("book.placesLeft", { n: s.available, cap: s.capacity })}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <button disabled={busy || !chosen} type="submit" className="w-full rounded-2xl bg-brand py-3 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "…" : t("track.rescheduleConfirm")}
        </button>
      </form>
    </dialog>
  );
}
