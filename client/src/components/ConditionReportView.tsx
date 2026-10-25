import { Camera, Gauge } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { ConditionPhoto, ConditionReport } from "../types";
import { CONDITION_ANGLES } from "./ConditionCapture";
import { useLanguage } from "../hooks/useLanguage";
import type { StringKey } from "../i18n/strings";

function Thumb({ photo, label, empty }: { photo?: ConditionPhoto; label: string; empty: string }) {
  if (!photo) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl bg-zinc-100 text-[11px] text-zinc-400 dark:bg-zinc-800">
        {empty}
      </div>
    );
  }
  return (
    <a href={photo.file} target="_blank" rel="noopener noreferrer" className="block">
      <img src={photo.file} alt={label} className="aspect-[4/3] w-full rounded-xl object-cover" />
    </a>
  );
}

/** Customer view: the car's condition at pickup next to its condition at delivery, angle by angle. */
export function ConditionReportView({ bookingId }: { bookingId: string | number }) {
  const { data } = useApi<ConditionReport>(`/api/bookings/${bookingId}/condition-report/`);
  const { t } = useLanguage();
  if (!data || (!data.pickup_photos.length && !data.delivery_photos.length && data.pickup_odometer_km == null)) return null;

  // Latest photo per angle for each stage
  const latest = (photos: ConditionPhoto[]) => new Map(photos.map((p) => [p.angle, p]));
  const before = latest(data.pickup_photos);
  const after = latest(data.delivery_photos);
  const angles = CONDITION_ANGLES.filter((a) => before.has(a.value) || after.has(a.value));

  return (
    <div className="glass rounded-3xl p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-zinc-400">
          <Camera size={16} className="text-[#ff4d2e]" /> {t("cr.title")}
        </h3>
        <div className="flex items-center gap-2 text-xs font-semibold">
          <Gauge size={14} className="text-[#ff4d2e]" />
          <span>{t("cr.pickup")}: {data.pickup_odometer_km != null ? `${data.pickup_odometer_km.toLocaleString("en-IN")} km` : "—"}</span>
          <span>· {t("cr.delivery")}: {data.delivery_odometer_km != null ? `${data.delivery_odometer_km.toLocaleString("en-IN")} km` : "—"}</span>
          {data.km_driven != null && (
            <span className="rounded-full bg-[#ff4d2e]/10 px-2 py-0.5 text-[#ff4d2e]">{t("cr.kmDriven", { n: data.km_driven })}</span>
          )}
        </div>
      </div>
      {angles.length > 0 && (
        <div className="space-y-3">
          <div className="grid grid-cols-[5rem_1fr_1fr] gap-2 text-[11px] font-bold uppercase text-zinc-400">
            <span />
            <span>{t("cr.before")}</span>
            <span>{t("cr.after")}</span>
          </div>
          {angles.map((a) => (
            <div key={a.value} className="grid grid-cols-[5rem_1fr_1fr] items-center gap-2">
              <span className="text-xs font-semibold">{t(`angle.${a.value}` as StringKey)}</span>
              <Thumb photo={before.get(a.value)} label={t("cr.before")} empty={t("cr.noPhoto")} />
              <Thumb photo={after.get(a.value)} label={t("cr.after")} empty={t("cr.noPhoto")} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
