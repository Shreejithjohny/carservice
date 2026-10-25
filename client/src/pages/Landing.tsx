import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, CarFront, ChevronRight, MapPin, ShieldCheck, Sparkles, Video } from "lucide-react";

export function Landing() {
  return (
    <div className="min-h-dvh bg-[#0b0d12] text-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="text-xl font-extrabold">Door<span className="text-[#ff4d2e]">Step</span></div>
        <div className="flex gap-2">
          <Link to="/login/driver" className="hidden rounded-full px-4 py-2 text-sm text-white/60 sm:inline-block">Staff sign in</Link>
          <Link to="/login" className="rounded-full px-4 py-2 text-sm text-white/80">Sign in</Link>
          <Link to="/register" className="rounded-full bg-[#ff4d2e] px-4 py-2 text-sm font-semibold">Create account</Link>
        </div>
      </header>
      <section className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-2">
        <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70"><MapPin size={14} className="text-[#ffb020]" /> Service that comes to you</div>
            <h1 className="mt-3 text-5xl font-extrabold leading-[1.05] md:text-6xl">Car care, delivered to your doorstep.</h1>
          <p className="mt-4 max-w-md text-white/60">
            Book a trusted pickup, follow your car in real time, and approve repairs with clear video proof.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/register" className="inline-flex items-center gap-2 rounded-full bg-[#ff4d2e] px-5 py-3 font-semibold">
              Book a service <ArrowRight size={16} />
            </Link>
            <Link to="/login" className="rounded-full border border-white/15 px-5 py-3">Sign in</Link>
          </div>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[32px] border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
        >
          <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-3 text-[#ffb020]"><CarFront size={18} /> Live service update</div><ChevronRight size={18} className="text-white/40" /></div>
          <p className="mt-3 text-2xl font-bold">Your car is in good hands.</p>
          <p className="mt-2 text-sm text-white/50">Pickup, repair, approvals, and delivery in one calm flow.</p>
          <div className="mt-6 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-2xl bg-white/10 p-3"><Sparkles size={16} className="mx-auto mb-1" /> Live tracking</div>
            <div className="rounded-2xl bg-white/10 p-3"><ShieldCheck size={16} className="mx-auto mb-1" /> Verified pickup</div>
            <div className="rounded-2xl bg-white/10 p-3"><Video size={16} className="mx-auto mb-1" /> Video proof</div>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
