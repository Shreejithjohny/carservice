import { useEffect, useState, useCallback } from "react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton, Empty } from "../components/States";
import { CarFront, Navigation, KeyRound, CheckCircle2, ShieldCheck, ExternalLink, Truck } from "lucide-react";
import { ConditionCapture } from "../components/ConditionCapture";
import type { Booking } from "../types";

// Matches the backend: drivers act only during the pickup stage of their assigned jobs.
const PICKUP_STAGE = ["Confirmed", "Pickup Scheduled", "Driver Assigned", "En Route for Pickup", "Arrived at Pickup"];
// Stages where the driver's phone shares GPS with the customer.
const GPS_STAGE = [...PICKUP_STAGE, "Vehicle Picked Up", "Out for Delivery"];

type OtpKind = "handover" | "delivery";

export function DriverDashboard() {
  const { data: pickups, loading, reload } = useApi<Booking[]>("/api/driver/pickups/");
  const { push } = useToast();

  const [otpModalBooking, setOtpModalBooking] = useState<Booking | null>(null);
  const [otpKind, setOtpKind] = useState<OtpKind>("handover");
  const [otpInput, setOtpInput] = useState("");
  // Test code returned by the backend only when OTP_BYPASS (demo mode) is on
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [gpsTrackingActive, setGpsTrackingActive] = useState<Record<string | number, boolean>>({});

  const activeJob = pickups?.find((b) => GPS_STAGE.includes(b.status));

  // Geolocation post helper
  const sendLocationUpdate = useCallback(
    async (bookingId: string | number, lat: number, lng: number) => {
      try {
        await api(`/api/driver/pickups/${bookingId}/location/`, {
          method: "POST",
          body: JSON.stringify({ latitude: lat, longitude: lng }),
        });
      } catch (err) {
        // Silent location post error fallback
      }
    },
    []
  );

  // Periodically send GPS location if tracking active for job
  useEffect(() => {
    if (!activeJob) return;
    const bId = activeJob.id || activeJob._id || activeJob.booking_reference;
    if (!gpsTrackingActive[bId]) return;

    const interval = setInterval(() => {
      if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            sendLocationUpdate(bId, pos.coords.latitude, pos.coords.longitude);
          },
          () => {
            // Geolocation error fallback
          },
          { enableHighAccuracy: true }
        );
      }
    }, 10000); // Every 10 seconds

    return () => clearInterval(interval);
  }, [activeJob, gpsTrackingActive, sendLocationUpdate]);

  async function handleStatusUpdate(booking: Booking, newStatus: string) {
    const bId = booking.id || booking._id || booking.booking_reference;
    try {
      await api(`/api/driver/pickups/${bId}/status/`, {
        method: "POST",
        body: JSON.stringify({ status: newStatus }),
      });
      push({ title: `Status updated to ${newStatus}` });
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to update status";
      push({ title: msg, tone: "err" });
    }
  }

  async function handleRequestOtp(booking: Booking, kind: OtpKind) {
    const bId = booking.id || booking._id || booking.booking_reference;
    try {
      const res = await api<{ message?: string; bypass_code?: string }>(
        `/api/driver/pickups/${bId}/${kind}-otp/request/`,
        { method: "POST" }
      );
      push({ title: `${kind === "handover" ? "Handover" : "Delivery"} OTP sent to the customer's app. Ask them for the 6-digit code.` });
      setOtpKind(kind);
      setOtpModalBooking(booking);
      setOtpInput("");
      setDemoCode(res.bypass_code ?? null);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to request OTP";
      push({ title: msg, tone: "err" });
    }
  }

  async function handleVerifyOtp(code: string = otpInput) {
    if (!otpModalBooking || !code.trim()) return;
    const bId = otpModalBooking.id || otpModalBooking._id || otpModalBooking.booking_reference;

    setVerifyingOtp(true);
    try {
      await api(`/api/driver/pickups/${bId}/${otpKind}-otp/verify/`, {
        method: "POST",
        body: JSON.stringify({ otp_code: code.trim() }),
      });
      push({
        title: otpKind === "handover" ? "Vehicle handover OTP verified! Status: Vehicle Picked Up" : "Delivery verified! Car handed back and booking completed.",
      });
      setOtpModalBooking(null);
      setOtpInput("");
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Invalid handover OTP code";
      push({ title: msg, tone: "err" });
    } finally {
      setVerifyingOtp(false);
    }
  }

  const toggleGps = (bookingId: string | number) => {
    // Side effects stay outside the state updater: React may run updaters twice in development.
    const next = !gpsTrackingActive[bookingId];
    setGpsTrackingActive((prev) => ({ ...prev, [bookingId]: next }));
    if (next && "geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition((pos) => {
        sendLocationUpdate(bookingId, pos.coords.latitude, pos.coords.longitude);
      });
      push({ title: "GPS location tracking enabled" });
    } else {
      push({ title: "GPS location tracking disabled" });
    }
  };

  if (loading) return <Skeleton className="h-96" />;
  if (!pickups?.length) return <Empty title="No assigned pickups" hint="You currently have no pending vehicle pickup jobs." />;

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <CarFront className="text-[#ff4d2e]" /> Driver / Valet Pickup Portal
        </h1>
        <p className="text-sm text-zinc-500">Manage vehicle pickups, customer handovers, and GPS route updates.</p>
      </div>

      {/* Handover OTP Modal */}
      {otpModalBooking && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass max-w-md w-full rounded-3xl p-6 space-y-4 text-center">
            <ShieldCheck size={48} className="mx-auto text-emerald-500" />
            <h3 className="text-xl font-extrabold">{otpKind === "handover" ? "Vehicle Handover Verification" : "Return Delivery Verification"}</h3>
            <p className="text-xs text-zinc-500">
              Ask customer <strong>{otpModalBooking.customer_name || "Customer"}</strong> for their 6-digit {otpKind} OTP code.
            </p>

            <input
              type="text"
              maxLength={6}
              className="w-full rounded-2xl border border-zinc-200 px-4 py-3 text-center font-mono text-3xl font-extrabold tracking-[0.4em] dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="000000"
              value={otpInput}
              onChange={(e) => setOtpInput(e.target.value)}
              autoFocus
            />

            <div className="grid grid-cols-2 gap-3 pt-2">
              <button
                onClick={() => setOtpModalBooking(null)}
                className="w-full rounded-2xl border border-zinc-200 py-3 text-xs font-bold dark:border-zinc-700"
              >
                Cancel
              </button>
              <button
                disabled={verifyingOtp}
                onClick={() => handleVerifyOtp()}
                className="w-full rounded-2xl bg-emerald-600 py-3 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {verifyingOtp ? "Verifying..." : otpKind === "handover" ? "Verify & Pick Up" : "Verify & Hand Back"}
              </button>
            </div>

            {demoCode && (
              <button
                type="button"
                onClick={() => handleVerifyOtp(demoCode)}
                className="w-full rounded-xl bg-zinc-100 dark:bg-zinc-800 py-2 text-[11px] font-bold text-zinc-600 dark:text-zinc-300 hover:bg-emerald-500 hover:text-white transition"
              >
                ⚡ Demo mode: use test code {demoCode}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Pickups List */}
      <div className="space-y-4">
        {pickups.map((b) => {
          const bId = b.id || b._id || b.booking_reference;
          const isTracking = gpsTrackingActive[bId];
          const gpsToggle = (
            <div className="flex items-center justify-between rounded-2xl border border-zinc-200 p-3 dark:border-zinc-700 text-xs">
              <div className="flex items-center gap-2">
                <Navigation size={16} className={isTracking ? "text-emerald-500 animate-pulse" : "text-zinc-400"} />
                <div>
                  <span className="font-bold block">Live GPS Location Sharing</span>
                  <span className="text-[11px] text-zinc-500">
                    {isTracking ? "Transmitting real-time GPS coordinates to customer map" : "GPS tracking inactive"}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => toggleGps(bId)}
                className={`rounded-xl px-3 py-1.5 font-bold transition ${
                  isTracking ? "bg-emerald-600 text-white" : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                }`}
              >
                {isTracking ? "Tracking Active" : "Enable GPS"}
              </button>
            </div>
          );

          return (
            <div key={bId} className="glass rounded-3xl p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 dark:border-zinc-800 pb-3">
                <div>
                  <span className="text-xs font-mono font-bold text-[#ff4d2e] bg-[#ff4d2e]/10 px-2.5 py-0.5 rounded-full">
                    {b.booking_reference || b.booking_id}
                  </span>
                  <h3 className="text-xl font-extrabold mt-1">
                    {b.vehicle_details ? `${b.vehicle_details.brand} ${b.vehicle_details.model}` : "Vehicle"}
                  </h3>
                  <p className="text-xs text-zinc-500 font-medium">
                    Reg: <strong>{b.vehicle_details?.registration_number || b.vehicle_details?.registration || "N/A"}</strong>
                  </p>
                </div>

                <div className="text-right">
                  <span className="rounded-full bg-[#ff4d2e]/15 px-3 py-1 text-xs font-bold text-[#ff4d2e]">
                    {b.status}
                  </span>
                  {b.handover_otp_verified && (
                    <span className="block mt-1 text-[11px] font-bold text-emerald-600 flex items-center justify-end gap-1">
                      <CheckCircle2 size={12} /> Handover Verified
                    </span>
                  )}
                </div>
              </div>

              {/* Customer & Location Box */}
              <div className="rounded-2xl bg-zinc-100/70 p-4 dark:bg-zinc-800/70 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 font-bold">Customer</span>
                  <span className="font-semibold">{b.customer_name || b.customer_email || "Customer"}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 font-bold">Phone</span>
                  <a href={`tel:${b.customer_phone}`} className="font-bold text-blue-600 dark:text-blue-400 underline">
                    {b.customer_phone || "Call Customer"}
                  </a>
                </div>
                <div className="pt-1">
                  <span className="text-zinc-500 font-bold block mb-0.5">Pickup Address</span>
                  <p className="font-medium text-zinc-700 dark:text-zinc-300">{b.pickup_address || b.address || "Address shared"}</p>
                </div>
                {b.pickup_latitude && b.pickup_longitude && (
                  <div className="pt-1 flex items-center justify-between">
                    <span className="text-zinc-500 font-bold">Map Coordinates</span>
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${b.pickup_latitude},${b.pickup_longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 font-bold text-[#ff4d2e] underline"
                    >
                      <ExternalLink size={13} /> Open Google Maps
                    </a>
                  </div>
                )}
              </div>

              {PICKUP_STAGE.includes(b.status) ? (
                <>
                  {gpsToggle}

                  <ConditionCapture bookingId={bId} stage="PICKUP" />

                  {/* Workflow Step Actions */}
                  <div className="space-y-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                    <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block mb-1">
                      Pickup Workflow Stage Controls
                    </span>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                      <button
                        onClick={() => handleStatusUpdate(b, "En Route for Pickup")}
                        className="rounded-xl border border-blue-200 bg-blue-50 py-2 font-bold text-blue-700 hover:bg-blue-100 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-400"
                      >
                        En Route
                      </button>

                      <button
                        onClick={() => handleStatusUpdate(b, "Arrived at Pickup")}
                        className="rounded-xl border border-amber-200 bg-amber-50 py-2 font-bold text-amber-700 hover:bg-amber-100 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-400"
                      >
                        Arrived at Location
                      </button>

                      <button
                        onClick={() => handleRequestOtp(b, "handover")}
                        className="col-span-2 sm:col-span-1 flex items-center justify-center gap-1 rounded-xl bg-[#ff4d2e] py-2 font-bold text-white hover:bg-[#e03e21]"
                      >
                        <KeyRound size={14} /> Handover OTP
                      </button>
                    </div>
                  </div>
                </>
              ) : b.status === "Ready for Delivery" ? (
                <button
                  onClick={() => handleStatusUpdate(b, "Out for Delivery")}
                  className="w-full flex items-center justify-center gap-2 rounded-2xl bg-blue-600 py-3 text-sm font-bold text-white hover:bg-blue-700"
                >
                  <Truck size={16} /> Start Return Delivery
                </button>
              ) : b.status === "Out for Delivery" ? (
                <>
                  {gpsToggle}
                  <ConditionCapture bookingId={bId} stage="DELIVERY" />
                  <button
                    onClick={() => handleRequestOtp(b, "delivery")}
                    className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#ff4d2e] py-3 text-sm font-bold text-white hover:bg-[#e03e21]"
                  >
                    <KeyRound size={16} /> Hand Back Car (Delivery OTP)
                  </button>
                </>
              ) : (
                <>
                  {b.status === "Vehicle Picked Up" && gpsToggle}
                  <p className="rounded-2xl bg-zinc-100 p-3 text-xs text-zinc-500 dark:bg-zinc-800/60">
                    {b.status === "Completed"
                      ? "Car delivered back to the customer — job complete."
                      : b.handover_otp_verified
                        ? "Vehicle handed over — pickup complete. You will be notified when it is ready to deliver back."
                        : `No driver actions while the booking is "${b.status}".`}
                  </p>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
