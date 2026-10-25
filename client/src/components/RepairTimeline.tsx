const STAGES = [
  "Inspection",
  "Issue Found",
  "Video Uploaded",
  "Waiting for Approval",
  "Repair Started",
  "Completed",
];

export function RepairTimeline({ stage }: { stage: string }) {
  const idx = Math.max(0, STAGES.indexOf(stage));
  return (
    <ol className="space-y-0">
      {STAGES.map((s, i) => (
        <li key={s} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span className={`h-3 w-3 rounded-full ${i <= idx ? "bg-brand" : "bg-zinc-300 dark:bg-zinc-700"}`} />
            {i < STAGES.length - 1 && <span className="w-px flex-1 bg-zinc-200 dark:bg-zinc-800 min-h-6" />}
          </div>
          <p className={`pb-5 text-sm ${i <= idx ? "font-semibold" : "text-zinc-500"}`}>{s}</p>
        </li>
      ))}
    </ol>
  );
}
