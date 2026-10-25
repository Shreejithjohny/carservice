import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/** Password input with a show/hide toggle. */
export function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: "current-password" | "new-password";
  hint?: string;
}) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <div className="text-xs font-semibold text-zinc-500">
      <label htmlFor={id}>{label}</label>
      <div className="relative mt-1">
        <input
          id={id}
          required
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          className="w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 pr-10 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex items-center px-3 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
      {hint && <p className="mt-1 font-normal text-[11px] text-zinc-400">{hint}</p>}
    </div>
  );
}

export const PASSWORD_HINT = "At least 8 characters, not all numbers, and not a common password.";
