import { Link } from "react-router-dom";
import { ArrowRight, Bell, Car, HeartPulse, History, IndianRupee, MapPin, Sparkles, Video, Wrench } from "lucide-react";
import { useAuth } from "../hooks/useAuth";

const tiles = [
  { to: "/app/book", title: "Book Service", icon: Wrench, hint: "Pickup in under 2 hours" },
  { to: "/app/vehicles", title: "My Vehicles", icon: Car, hint: "Garage & RC details" },
  { to: "/app/track", title: "Active Services", icon: Sparkles, hint: "Live job status" },
  { to: "/app/history", title: "Service History", icon: History, hint: "Past jobs" },
  { to: "/app/estimate", title: "Cost Estimator", icon: IndianRupee, hint: "Symptom → price band" },
  { to: "/app/health", title: "Car Health", icon: HeartPulse, hint: "Score, badges, trend" },
  { to: "/app/notifications", title: "Notifications", icon: Bell, hint: "Approvals & valet" },
  { to: "/app/approvals", title: "Video approvals", icon: Video, hint: "Transparent extras" },
];

export function Dashboard() {
  const { user } = useAuth();
  return (
    <div className="space-y-6">
      <div className="glass overflow-hidden rounded-3xl p-6">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-zinc-400"><MapPin size={14} className="text-[#ff4d2e]" /> Pickup location</div>
        <h2 className="mt-2 text-3xl font-extrabold">Good to see you, {user?.name.split(" ")[0]}</h2>
        <p className="mt-1 text-sm text-zinc-500">Where should we pick up your car today?</p>
        <Link to="/app/book" className="mt-5 flex items-center justify-between rounded-2xl bg-[#ff4d2e] px-4 py-3 font-bold text-white transition hover:bg-[#e94529]"><span>Book a doorstep service</span><ArrowRight size={18} /></Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className="glass group rounded-3xl p-5 transition hover:-translate-y-0.5">
            <t.icon className="text-[#ff4d2e]" size={22} />
            <h3 className="mt-3 text-lg font-bold">{t.title}</h3>
            <p className="text-sm text-zinc-500">{t.hint}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
