import { Link } from "react-router-dom";
import { ArrowRight, Bell, Car, HeartPulse, History, IndianRupee, MapPin, Sparkles, Video, Wrench } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useLanguage } from "../hooks/useLanguage";
import { ServiceReminders } from "../components/ServiceReminders";

const tiles = [
  { to: "/app/book", key: "book", icon: Wrench },
  { to: "/app/vehicles", key: "vehicles", icon: Car },
  { to: "/app/track", key: "track", icon: Sparkles },
  { to: "/app/history", key: "history", icon: History },
  { to: "/app/estimate", key: "estimate", icon: IndianRupee },
  { to: "/app/health", key: "health", icon: HeartPulse },
  { to: "/app/notifications", key: "alerts", icon: Bell },
  { to: "/app/approvals", key: "approvals", icon: Video },
] as const;

export function Dashboard() {
  const { user } = useAuth();
  const { t } = useLanguage();
  return (
    <div className="space-y-6">
      <ServiceReminders />
      <div className="glass overflow-hidden rounded-3xl p-6">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-zinc-400"><MapPin size={14} className="text-[#ff4d2e]" /> {t("dash.pickupLocation")}</div>
        <h2 className="mt-2 text-3xl font-extrabold">{t("dash.greeting", { name: user?.name.split(" ")[0] ?? "" })}</h2>
        <p className="mt-1 text-sm text-zinc-500">{t("dash.question")}</p>
        <Link to="/app/book" className="mt-5 flex items-center justify-between rounded-2xl bg-[#ff4d2e] px-4 py-3 font-bold text-white transition hover:bg-[#e94529]"><span>{t("dash.bookCta")}</span><ArrowRight size={18} /></Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((tile) => (
          <Link key={tile.to} to={tile.to} className="glass group rounded-3xl p-5 transition hover:-translate-y-0.5">
            <tile.icon className="text-[#ff4d2e]" size={22} />
            <h3 className="mt-3 text-lg font-bold">{t(`dash.tile.${tile.key}`)}</h3>
            <p className="text-sm text-zinc-500">{t(`dash.tile.${tile.key}Hint`)}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
