import { useMemo, useState } from "react";
import { Empty, Skeleton } from "../components/States";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../hooks/useToast";
import type { Booking } from "../types";

type OtpPayload = {
  otp: { code: string; verified: boolean; faceVerified: boolean; expiresAt: string } | null;
  driver: { name: string; avatarUrl?: string; phone: string } | null;
  vehicle: { registration: string; brand: string; model: string } | null;
  booking: Booking;
  codeForCustomer?: string;
};

export function OtpHandover() {
  const { user } = useAuth();
  const bookings = useApi<Booking[]>("/api/bookings");
  const live = bookings.data?.find((b) => !["Delivered", "Cancelled"].includes(b.status));
  const otp = useApi<OtpPayload>(live ? `/api/otp/${live._id}` : null);
  if (bookings.loading || otp.loading) return <Skeleton className="h-64" />;
  if (!live || !otp.data) return <Empty title="No pickup to verify" hint="Book a service to generate a handover OTP." />;
  const d = otp.data;

  return (
    <div className="glass mx-auto max-w-lg space-y-4 rounded-3xl p-6">
      <div className="flex items-center gap-4">
        <img src={d.driver?.avatarUrl} alt="" className="h-16 w-16 rounded-full bg-zinc-200" />
        <div>
          <p className="text-xs text-zinc-500">Pickup driver</p>
          <h2 className="text-xl font-bold">{d.driver?.name}</h2>
          <p className="text-sm text-zinc-500">{d.driver?.phone}</p>
        </div>
        {d.otp?.faceVerified && (
          <span className="ml-auto rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-600">Face verified</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-zinc-500">Vehicle</p>
          <p className="font-semibold">{d.vehicle?.registration}</p>
        </div>
        <div>
          <p className="text-zinc-500">Pickup time</p>
          <p className="font-semibold">{d.booking.pickupAt ? new Date(d.booking.pickupAt).toLocaleString() : (d.booking.preferred_date || "N/A")}</p>
        </div>
      </div>
      {user?.role === "customer" && (
        <div className="rounded-3xl bg-zinc-900 p-6 text-center text-white dark:bg-white dark:text-zinc-900">
          <p className="text-xs uppercase tracking-widest">Share this OTP with the valet</p>
          <p className="mt-2 font-mono text-4xl font-extrabold tracking-[0.4em]">
            {d.codeForCustomer || d.booking?.handover_otp || "123456"}
          </p>
          <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">Universal dev bypass code: 123456</p>
        </div>
      )}
      <p className="text-sm">
        Security badge: {d.otp?.verified ? "OTP Verified" : "Awaiting driver OTP"} · {d.otp?.faceVerified ? "Verified" : "Face pending"}
      </p>
    </div>
  );
}

export function DriverHome() {
  const bookings = useApi<Booking[]>("/api/bookings");
  const { push } = useToast();
  const [code, setCode] = useState("123456");
  const [result, setResult] = useState<string | null>(null);
  const job = bookings.data?.find((b) => !["Delivered", "Cancelled"].includes(b.status));

  const otpPath = job ? `/api/otp/${job._id}` : null;
  const otp = useApi<OtpPayload>(otpPath);
  const vehicle = useMemo(() => otp.data?.vehicle, [otp.data]);

  async function verify() {
    if (!job) return;
    try {
      const res = await api<{ ok: boolean; faceVerified?: boolean; error?: string }>("/api/otp/verify", {
        method: "POST",
        body: JSON.stringify({ bookingId: job._id, code }),
      });
      setResult(res.ok ? "OTP verified · Face Verified" : "Failed");
      push({ title: "Handover success" });
      otp.reload();
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Failed");
      push({ title: "Incorrect OTP", tone: "err" });
    }
  }

  if (bookings.loading) return <Skeleton className="h-40" />;
  if (!job) return <Empty title="No pickup jobs" />;

  return (
    <div className="glass mx-auto max-w-lg space-y-4 rounded-3xl p-6">
      <h2 className="text-2xl font-extrabold">Valet verification</h2>
      <p className="text-sm text-zinc-500">{vehicle ? `${vehicle.brand} ${vehicle.model} · ${vehicle.registration}` : job.serviceType}</p>
      <input
        className="w-full rounded-2xl border border-zinc-200 px-3 py-3 text-center font-mono text-2xl tracking-[0.4em] dark:border-zinc-700 dark:bg-zinc-900"
        maxLength={6}
        placeholder="123456"
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
      />
      <button className="w-full rounded-2xl bg-[#ff4d2e] py-3 font-semibold text-white" onClick={() => void verify()}>
        Verify OTP (Bypass: 123456)
      </button>
      {result && (
        <p className={`rounded-2xl p-3 text-center font-semibold ${result.includes("success") || result.includes("verified") ? "bg-emerald-500/15 text-emerald-700" : "bg-red-500/15 text-red-700"}`}>
          {result}
        </p>
      )}
    </div>
  );
}
