import { motion } from "framer-motion";

export function ProgressRing({ value, label }: { value: number; label: string }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.min(100, Math.max(0, value)) / 100) * c;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-[120px] w-[120px]">
        <svg width="120" height="120" viewBox="0 0 120 120" className="-rotate-90">
          <circle cx="60" cy="60" r={r} fill="none" className="stroke-zinc-200 dark:stroke-zinc-800" strokeWidth="10" />
          <motion.circle
            cx="60"
            cy="60"
            r={r}
            fill="none"
            stroke={`url(#ring-${label.replace(/\s/g, "")})`}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.1, ease: "easeOut" }}
          />
          <defs>
            <linearGradient id={`ring-${label.replace(/\s/g, "")}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#ff4d2e" />
              <stop offset="100%" stopColor="#ffb020" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 grid place-items-center text-2xl font-bold">{value}</div>
      </div>
      <div className="text-xs font-medium text-zinc-500">{label}</div>
    </div>
  );
}
