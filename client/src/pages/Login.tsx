import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { Building2, Car, Shield, Truck, Wrench, Sparkles } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import { ApiError } from "../services/api";
import { PasswordField } from "../components/PasswordField";
import { homePathForRole } from "../utils/roles";
import type { Role } from "../types";

// One sign-in page, one tab per role; each tab has its own URL (/login/driver ...) staff can bookmark.
const SIGN_IN_TABS = [
  { slug: "customer", role: "customer", label: "Customer", icon: Car, blurb: "Book, track and pay for your car service.", demo: "customer@smartdoorstep.com" },
  { slug: "driver", role: "driver", label: "Driver", icon: Truck, blurb: "Your pickup and delivery jobs.", demo: "driver@smartdoorstep.com" },
  { slug: "mechanic", role: "mechanic", label: "Mechanic", icon: Wrench, blurb: "Your assigned service jobs.", demo: "mechanic@smartdoorstep.com" },
  { slug: "manager", role: "service_center_manager", label: "Manager", icon: Building2, blurb: "Run your service center.", demo: "manager@smartdoorstep.com" },
  { slug: "admin", role: "admin", label: "Admin", icon: Shield, blurb: "Platform administration.", demo: "admin@smartdoorstep.com" },
] as const satisfies readonly { slug: string; role: Role; label: string; icon: typeof Car; blurb: string; demo: string }[];

const INPUT =
  "mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 focus:ring-2 focus:ring-[#ff4d2e]";

export function Login() {
  const { slug = "customer" } = useParams();
  const tab = SIGN_IN_TABS.find((t) => t.slug === slug);
  if (!tab) return <Navigate to="/login/customer" replace />;
  // key: switching tabs starts with an empty form
  return <SignInForm key={tab.slug} tab={tab} />;
}

function SignInForm({ tab }: Readonly<{ tab: (typeof SIGN_IN_TABS)[number] }>) {
  const { passwordLogin, sendOtp, bypassLogin, demoMode } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  // Set when the account belongs to another tab, e.g. a driver signing in on the Customer tab
  const [otherRole, setOtherRole] = useState<string | null>(null);
  const isCustomer = tab.role === "customer";

  async function run(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      const accountRole = err instanceof ApiError ? (err.data?.account_role as string | undefined) : undefined;
      setOtherRole(accountRole ?? null);
      push({ title: err instanceof ApiError ? err.message : "Sign in failed", tone: "err" });
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void run(async () => {
      const user = await passwordLogin(identifier.trim(), password, tab.role);
      push({ title: `Welcome back, ${user.name}!` });
      void navigate(homePathForRole(user.role));
    });
  }

  function onOtp() {
    if (!identifier.trim()) return push({ title: "Enter your email or mobile number first", tone: "err" });
    void run(async () => {
      const res = await sendOtp(identifier.trim());
      push({ title: res.message || `Verification code sent to ${identifier}` });
      void navigate("/verify-otp", { state: { identifier: identifier.trim() } });
    });
  }

  function onDemo() {
    void run(async () => {
      const user = await bypassLogin(tab.demo, tab.role);
      push({ title: `Signed in to the demo ${tab.label.toLowerCase()} account` });
      void navigate(homePathForRole(user.role));
    });
  }

  const other = otherRole ? SIGN_IN_TABS.find((t) => t.role === otherRole.toLowerCase()) : undefined;

  return (
    <div className="min-h-dvh bg-[#f6f3ee] px-4 py-10 text-zinc-900 dark:bg-[#07080c] dark:text-white">
      <div className="mx-auto w-full max-w-md">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-xl font-extrabold">
            Door<span className="text-[#ff4d2e]">Step</span>
          </Link>
          <Link to="/" className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300">
            ← Home
          </Link>
        </div>

        {/* Role tabs */}
        <nav aria-label="Sign in as" className="mt-8 grid grid-cols-5 gap-1 rounded-2xl bg-zinc-200/70 p-1 dark:bg-zinc-800/70">
          {SIGN_IN_TABS.map((t) => {
            const active = t.slug === tab.slug;
            return (
              <Link
                key={t.slug}
                to={`/login/${t.slug}`}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-1 rounded-xl px-1 py-2 text-[11px] font-bold transition ${
                  active ? "bg-white text-[#ff4d2e] shadow-sm dark:bg-zinc-900" : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                }`}
              >
                <t.icon size={18} />
                {t.label}
              </Link>
            );
          })}
        </nav>

        <div className="glass mt-4 rounded-3xl p-6">
          <h1 className="text-2xl font-extrabold">{tab.label} sign in</h1>
          <p className="mt-1 text-sm text-zinc-500">{tab.blurb}</p>

          <form className="mt-5 space-y-4" onSubmit={onSubmit}>
            <label className="block text-xs font-semibold text-zinc-500">
              <span>{isCustomer ? "Email or mobile number" : "Work email or mobile number"}</span>
              <input
                required
                autoComplete="username"
                className={INPUT}
                placeholder={isCustomer ? "you@example.com" : "name@smartdoorstep.com"}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </label>
            <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="current-password" />

            {other && (
              <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                This is a {other.label} account.{" "}
                <Link to={`/login/${other.slug}`} className="font-bold underline">
                  Go to {other.label} sign in
                </Link>
              </p>
            )}

            <button
              disabled={busy}
              type="submit"
              className="w-full rounded-2xl bg-[#ff4d2e] py-3 text-sm font-semibold text-white shadow-md shadow-[#ff4d2e]/20 transition hover:bg-[#e94529] disabled:opacity-50"
            >
              {busy ? "Please wait..." : "Sign in"}
            </button>

            <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold">
              <Link to="/forgot-password" state={{ identifier }} className="text-[#ff4d2e] hover:underline">
                Forgot password?
              </Link>
              {isCustomer && (
                <button type="button" disabled={busy} onClick={onOtp} className="text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-300">
                  Use a one-time code instead
                </button>
              )}
            </div>
          </form>

          {demoMode && (
            <button
              type="button"
              disabled={busy}
              onClick={onDemo}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-[#ff4d2e]/50 py-2.5 text-xs font-semibold text-[#ff4d2e] hover:bg-[#ff4d2e]/5 disabled:opacity-50"
            >
              <Sparkles size={14} /> Try the demo {tab.label.toLowerCase()} account
            </button>
          )}
        </div>

        <p className="mt-5 text-center text-sm text-zinc-500">
          {isCustomer ? (
            <>
              New to DoorStep?{" "}
              <Link to="/register" className="font-semibold text-[#ff4d2e] hover:underline">
                Create an account
              </Link>
            </>
          ) : (
            "Staff accounts are created by your administrator."
          )}
        </p>
      </div>
    </div>
  );
}
