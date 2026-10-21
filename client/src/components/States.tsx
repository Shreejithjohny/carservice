export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-2xl bg-zinc-200/80 dark:bg-zinc-800 ${className}`} />;
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="glass rounded-3xl p-10 text-center text-zinc-500">
      <p className="font-semibold text-zinc-800 dark:text-zinc-200">{title}</p>
      {hint && <p className="mt-1 text-sm">{hint}</p>}
    </div>
  );
}
