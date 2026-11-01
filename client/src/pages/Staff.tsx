import { useState } from "react";
import { Check, Copy, UserPlus, Users, Wand2 } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { api, ApiError } from "../services/api";
import { Empty, Skeleton } from "../components/States";
import { PasswordField } from "../components/PasswordField";
import type { ServiceCenter } from "../types";

type StaffMember = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: "DRIVER" | "MECHANIC";
  service_center: { id: number; name: string } | null;
  speciality: string;
  is_available: boolean;
};

const INPUT = "mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const ROLE_LABEL = { DRIVER: "Driver", MECHANIC: "Mechanic" } as const;
const SIGN_IN_TAB = { DRIVER: "/login/driver", MECHANIC: "/login/mechanic" } as const;

/** A random 12-character password without look-alike characters (from the browser's secure random source). */
function generatePassword(): string {
  const letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ";
  const all = `${letters}23456789`;
  const bytes = crypto.getRandomValues(new Uint32Array(12));
  const chars = Array.from(bytes, (b) => all[b % all.length]);
  // At least one letter and one digit, so Django's "entirely numeric" rule can never reject it
  chars[0] = letters[bytes[0] % letters.length];
  chars[11] = "23456789"[bytes[11] % 8];
  return chars.join("");
}

const EMPTY_FORM = { role: "DRIVER" as StaffMember["role"], name: "", email: "", phone: "", password: "", service_center: "", speciality: "" };

/**
 * Admins add drivers and mechanics to any workshop; managers to their own. The new person signs in
 * on their own tab with the email and password set here, and can change the password afterwards.
 */
export function Staff() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { push } = useToast();
  const { data: staff, loading, reload } = useApi<StaffMember[]>("/api/staff/");
  const { data: centers } = useApi<ServiceCenter[]>(isAdmin ? "/api/service-centers/" : null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ member: StaffMember; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const set = (key: keyof typeof EMPTY_FORM) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit() {
    setSaving(true);
    setError(null);
    try {
      const body = { ...form, service_center: isAdmin ? Number(form.service_center) || undefined : undefined };
      const member = await api<StaffMember>("/api/staff/", { method: "POST", body: JSON.stringify(body) });
      setCreated({ member, password: form.password });
      setCopied(false);
      setForm({ ...EMPTY_FORM, role: form.role, service_center: form.service_center });
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add this person. Check the details and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function setAvailable(member: StaffMember, isAvailable: boolean) {
    try {
      await api(`/api/staff/${member.id}/`, { method: "PATCH", body: JSON.stringify({ is_available: isAvailable }) });
      push({ title: `${member.name} is now ${isAvailable ? "on duty" : "off duty"}` });
      reload();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Could not update", tone: "err" });
    }
  }

  const signInDetails = created
    ? `Sign in at ${globalThis.location.origin}${SIGN_IN_TAB[created.member.role]}\nEmail: ${created.member.email}\nPassword: ${created.password}`
    : "";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold">
          <Users className="text-brand-fg" /> Staff
        </h1>
        <p className="text-sm text-zinc-500">
          {isAdmin ? "Add drivers and mechanics to any service center." : "Add drivers and mechanics to your service center."} Off-duty staff are
          skipped by automatic assignment.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void onSubmit();
        }}
        className="glass space-y-4 rounded-3xl p-6" aria-label="Add a driver or mechanic">
        <h2 className="flex items-center gap-2 text-lg font-bold">
          <UserPlus size={18} className="text-brand-fg" /> Add a driver or mechanic
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-xs font-semibold text-zinc-500">
            <span>Role</span>
            <select className={INPUT} value={form.role} onChange={(e) => set("role")(e.target.value)}>
              <option value="DRIVER">Driver (pickup valet)</option>
              <option value="MECHANIC">Mechanic</option>
            </select>
          </label>
          {isAdmin && (
            <label className="block text-xs font-semibold text-zinc-500">
              <span>Service center</span>
              <select required className={INPUT} value={form.service_center} onChange={(e) => set("service_center")(e.target.value)}>
                <option value="">Choose…</option>
                {centers?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="block text-xs font-semibold text-zinc-500">
            <span>Full name</span>
            <input required minLength={2} className={INPUT} value={form.name} onChange={(e) => set("name")(e.target.value)} />
          </label>
          <label className="block text-xs font-semibold text-zinc-500">
            <span>Work email (used to sign in)</span>
            <input required type="email" autoComplete="off" className={INPUT} value={form.email} onChange={(e) => set("email")(e.target.value)} />
          </label>
          <label className="block text-xs font-semibold text-zinc-500">
            <span>Mobile number (optional)</span>
            <input type="tel" className={INPUT} value={form.phone} onChange={(e) => set("phone")(e.target.value)} />
          </label>
          {form.role === "MECHANIC" && (
            <label className="block text-xs font-semibold text-zinc-500">
              <span>Speciality (optional)</span>
              <input className={INPUT} placeholder="e.g. AC and electricals" value={form.speciality} onChange={(e) => set("speciality")(e.target.value)} />
            </label>
          )}
          <div className="sm:col-span-2">
            <PasswordField label="First password" value={form.password} onChange={set("password")} autoComplete="new-password" />
            <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-zinc-500">
              <span>Share it with them; they can change it later from the key icon.</span>
              <button type="button" onClick={() => set("password")(generatePassword())} className="flex shrink-0 items-center gap-1 font-bold text-brand-fg hover:underline">
                <Wand2 size={12} /> Generate
              </button>
            </div>
          </div>
        </div>
        {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</p>}
        <button disabled={saving} className="rounded-2xl bg-brand px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50">
          {saving ? "Adding…" : `Add ${ROLE_LABEL[form.role].toLowerCase()}`}
        </button>
      </form>

      {created && (
        <section aria-label="New account" className="space-y-2 rounded-3xl border border-emerald-200 bg-emerald-50 p-5 text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30">
          <p className="font-bold text-emerald-800 dark:text-emerald-300">
            {created.member.name} can now sign in as a {ROLE_LABEL[created.member.role].toLowerCase()}. Share these details with them; the password is not shown again.
          </p>
          <pre className="whitespace-pre-wrap rounded-xl bg-white p-3 font-mono text-xs text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{signInDetails}</pre>
          <button
            type="button"
            onClick={() =>
              void navigator.clipboard?.writeText(signInDetails).then(
                () => setCopied(true),
                () => setCopied(false)
              )
            }
            className="flex items-center gap-1.5 text-xs font-bold text-emerald-800 hover:underline dark:text-emerald-300"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy sign-in details"}
          </button>
        </section>
      )}

      <section className="glass space-y-3 rounded-3xl p-6">
        <h2 className="text-lg font-bold">Team</h2>
        {loading && !staff && <Skeleton className="h-32" />}
        {staff && !staff.length && <Empty title="No drivers or mechanics yet" hint="Add the first one above." />}
        {!!staff?.length && (
          <ul className="divide-y divide-zinc-200/70 dark:divide-zinc-800">
            {staff.map((m) => (
              <li key={m.id} aria-label={m.name} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <div className="min-w-0">
                  <p className="font-bold">
                    {m.name}{" "}
                    <span className="ml-1 rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-bold text-brand-fg">{ROLE_LABEL[m.role]}</span>
                  </p>
                  <p className="truncate text-xs text-zinc-500">
                    {[m.email, m.phone, isAdmin ? m.service_center?.name : null, m.speciality].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <button
                  type="button"
                  aria-pressed={m.is_available}
                  onClick={() => void setAvailable(m, !m.is_available)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-bold ${
                    m.is_available ? "bg-emerald-600 text-white" : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                  }`}
                >
                  {m.is_available ? "On duty" : "Off duty"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
