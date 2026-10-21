import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Check } from "lucide-react";

interface Option {
  id: number | string;
  name: string;
  sublabel?: string;
}

interface SearchableSelectProps {
  label: string;
  placeholder?: string;
  options: Option[];
  value?: number | string;
  onChange: (id: number | string, option: Option | null) => void;
  disabled?: boolean;
  loading?: boolean;
  emptyText?: string;
}

export function SearchableSelect({
  label,
  placeholder = "Select...",
  options,
  value,
  onChange,
  disabled = false,
  loading = false,
  emptyText = "No options found",
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((o) => String(o.id) === String(value));

  const filteredOptions = options.filter(
    (o) =>
      o.name.toLowerCase().includes(search.toLowerCase()) ||
      (o.sublabel && o.sublabel.toLowerCase().includes(search.toLowerCase()))
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative space-y-1" ref={containerRef}>
      <label className="block text-xs font-semibold text-zinc-500 uppercase tracking-wider">{label}</label>

      <button
        type="button"
        disabled={disabled || loading}
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-left text-sm transition dark:border-zinc-700 dark:bg-zinc-900 ${
          disabled ? "opacity-50 cursor-not-allowed bg-zinc-100 dark:bg-zinc-800" : "hover:border-zinc-300 dark:hover:border-zinc-600"
        } ${open ? "ring-2 ring-[#ff4d2e]" : ""}`}
      >
        <span className={selectedOption ? "font-semibold text-zinc-900 dark:text-zinc-100" : "text-zinc-400"}>
          {loading ? "Loading..." : selectedOption ? selectedOption.name : placeholder}
        </span>
        <ChevronDown size={18} className={`text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && !disabled && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-700 dark:bg-zinc-900">
          <div className="border-b border-zinc-200 p-2 dark:border-zinc-800">
            <div className="flex items-center gap-2 rounded-xl bg-zinc-100 px-3 py-1.5 dark:bg-zinc-800">
              <Search size={14} className="text-zinc-400 shrink-0" />
              <input
                autoFocus
                className="w-full bg-transparent text-xs text-zinc-900 outline-none dark:text-zinc-100"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="max-h-44 overflow-y-auto p-1">
            {filteredOptions.length === 0 ? (
              <p className="p-3 text-center text-xs text-zinc-400">{emptyText}</p>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = String(opt.id) === String(value);
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      onChange(opt.id, opt);
                      setOpen(false);
                      setSearch("");
                    }}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-xs font-medium transition ${
                      isSelected
                        ? "bg-[#ff4d2e] text-white font-bold"
                        : "text-zinc-800 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800"
                    }`}
                  >
                    <div>
                      <span>{opt.name}</span>
                      {opt.sublabel && (
                        <span className={`ml-2 text-[10px] ${isSelected ? "text-white/80" : "text-zinc-400"}`}>
                          · {opt.sublabel}
                        </span>
                      )}
                    </div>
                    {isSelected && <Check size={14} />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
