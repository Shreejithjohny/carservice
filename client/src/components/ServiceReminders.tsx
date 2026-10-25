import { Link } from "react-router-dom";
import { CalendarClock } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useLanguage } from "../hooks/useLanguage";
import type { ServiceDue } from "../types";

/** Dashboard banner for cars that are due or overdue for their periodic service. */
export function ServiceReminders() {
  const { data } = useApi<ServiceDue[]>("/api/reminders/");
  const { t } = useLanguage();

  // Built here from the numbers (not the API's English text) so it follows the chosen language
  const reasons = (d: ServiceDue) => {
    const out: string[] = [];
    if (d.days_left < 0) out.push(t("rem.daysPast", { n: -d.days_left }));
    else if (d.days_left <= 14) out.push(t("rem.daysLeft", { n: d.days_left }));
    if (d.km_left != null) {
      if (d.km_left < 0) out.push(t("rem.kmPast", { n: (-d.km_left).toLocaleString("en-IN") }));
      else if (d.km_left <= 1000) out.push(t("rem.kmLeft", { n: d.km_left.toLocaleString("en-IN") }));
    }
    return out.join(" · ");
  };
  const due = (data ?? []).filter((d) => d.status === "OVERDUE" || d.status === "DUE_SOON");
  if (!due.length) return null;

  return (
    <div className="space-y-2">
      {due.map((d) => (
        <div
          key={d.vehicle}
          className={`flex flex-wrap items-center justify-between gap-3 rounded-3xl border p-4 ${
            d.status === "OVERDUE"
              ? "border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/30"
              : "border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30"
          }`}
        >
          <div className="flex items-start gap-3">
            <CalendarClock size={20} className={d.status === "OVERDUE" ? "text-red-600" : "text-amber-600"} />
            <div>
              <p className="font-bold">
                {t(d.status === "OVERDUE" ? "rem.overdue" : "rem.dueSoon")}: {d.name} ({d.registration_number})
              </p>
              <p className="text-xs text-zinc-600 dark:text-zinc-400">{reasons(d)}</p>
            </div>
          </div>
          <Link to={`/app/book?vehicle=${d.vehicle}`} className="rounded-2xl bg-[#ff4d2e] px-4 py-2 text-sm font-bold text-white">
            {t("rem.bookNow")}
          </Link>
        </div>
      ))}
    </div>
  );
}
