import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { Clock3, Navigation, Route, XCircle, AlertTriangle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { useLanguage, useStatusLabel } from "../hooks/useLanguage";
import { Empty, Skeleton } from "../components/States";
import type { Booking } from "../types";
import { LiveTrackingMap, type RoutePoint } from "../components/LiveTrackingMap";
import { ConditionReportView } from "../components/ConditionReportView";
import { ReviewForm } from "../components/ReviewForm";

const STEPS = [
  "Booking Created",
  "Confirmed",
  "Pickup Scheduled",
  "Driver Assigned",
  "Vehicle Picked Up",
  "In Service",
  "Repair Approval Required",
  "Ready for Delivery",
  "Out for Delivery",
  "Completed",
];

export function Track() {
  const { data, loading, reload } = useApi<Booking[]>("/api/bookings/");
  const { push } = useToast();
  const [cancelling, setCancelling] = useState(false);
  const [selectedId, setSelectedId] = useState<string | number>("");
  const { t } = useLanguage();
  const statusLabel = useStatusLabel();

  const active = useMemo(
    () => data?.filter((b) => !["Completed", "Delivered", "Cancelled"].includes(b.status)) ?? [],
    [data]
  );

  const booking = useMemo(() => {
    if (!data || data.length === 0) return null;
    if (selectedId) {
      return data.find((b) => String(b.id || b._id || b.booking_reference) === String(selectedId)) || data[0];
    }
    return active[0] || data[0];
  }, [data, selectedId, active]);

  const bookingId = booking?.id || booking?._id || booking?.booking_reference;

  // Rich tracking detail payload
  const { data: trackingData, reload: reloadTracking } = useApi<any>(bookingId ? `/api/bookings/${bookingId}/tracking/` : null);

  // Poll for new driver GPS points while the booking is still in progress
  const isFinished = !booking || ["Completed", "Delivered", "Cancelled"].includes(booking.status);
  useEffect(() => {
    if (!bookingId || isFinished) return;
    const t = setInterval(reloadTracking, 10000);
    return () => clearInterval(t);
    // reloadTracking is recreated every render; the interval only needs to restart when the booking changes
  }, [bookingId, isFinished]);

  if (loading) return <Skeleton className="h-64" />;
  if (!booking) return <Empty title={t("track.none")} hint={t("track.noneHint")} />;

  const serviceName = booking.service_type_details?.name || booking.serviceType || "Vehicle Service";
  const vehicleName = booking.vehicle_details
    ? `${booking.vehicle_details.brand} ${booking.vehicle_details.model}`
    : "Your Vehicle";
  const regNumber = booking.vehicle_details?.registration_number || booking.vehicle_details?.registration || "";
  const centerName = booking.service_center_details?.name || "Doorstep Service Hub";
  const address = booking.pickup_address || booking.address || "Pickup address shared";
  const cost = booking.estimated_cost || booking.estimatedCost || "0";
  const refCode = booking.booking_reference || booking.booking_id || `#${bookingId}`;

  const currentStatus = booking.status || "Pending";
  const isCancellable = ["Pending", "Confirmed", "PENDING", "CONFIRMED"].includes(currentStatus);

  // Status mapping to the timeline steps
  let currentStepIdx = 0;
  if (currentStatus === "Pending") currentStepIdx = 0;
  else if (currentStatus === "Confirmed") currentStepIdx = 1;
  else if (currentStatus === "Pickup Scheduled") currentStepIdx = 2;
  else if (currentStatus === "Driver Assigned" || currentStatus === "En Route for Pickup" || currentStatus === "Arrived at Pickup") currentStepIdx = 3;
  else if (currentStatus === "Vehicle Picked Up") currentStepIdx = 4;
  else if (currentStatus === "In Service") currentStepIdx = 5;
  else if (currentStatus === "Repair Approval Required") currentStepIdx = 6;
  else if (currentStatus === "Ready for Delivery") currentStepIdx = 7;
  else if (currentStatus === "Out for Delivery") currentStepIdx = 8;
  else if (currentStatus === "Completed" || currentStatus === "Delivered") currentStepIdx = 9;

  const driver = trackingData?.assigned_driver || booking.assigned_driver_details;
  const mechanic = trackingData?.assigned_mechanic || booking.assigned_mechanic_details;
  const otpCode = trackingData?.handover_otp_code || booking.handover_otp;
  const deliveryOtp: string | null = trackingData?.delivery_otp_code ?? null;
  const pickupPoint: [number, number] | null =
    booking.pickup_latitude != null && booking.pickup_longitude != null
      ? [Number(booking.pickup_latitude), Number(booking.pickup_longitude)]
      : null;
  const hubPoint: [number, number] | null =
    booking.service_center_details?.latitude != null && booking.service_center_details?.longitude != null
      ? [Number(booking.service_center_details.latitude), Number(booking.service_center_details.longitude)]
      : null;

  const isOnTheWay = ["Pickup Scheduled", "Driver Assigned", "En Route for Pickup", "Arrived at Pickup", "Out for Delivery"].includes(currentStatus);

  // Where the driver is going now: the map draws the route there and shows the ETA. A confirmed
  // booking with a driver already assigned means the driver is on the way to pick the car up.
  let driverHeading: "pickup" | "hub" | null = null;
  if (isOnTheWay || (currentStatus === "Confirmed" && driver)) driverHeading = "pickup";
  else if (currentStatus === "Vehicle Picked Up") driverHeading = "hub";

  async function handleCancelBooking() {
    if (!isCancellable) return;
    if (!window.confirm(t("track.cancelConfirm"))) return;

    setCancelling(true);
    try {
      await api(`/api/bookings/${bookingId}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: "Cancelled" }),
      });
      push({ title: "Booking cancelled successfully" });
      reload();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Failed to cancel booking";
      push({ title: msg, tone: "err" });
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Booking Selector Dropdown if multiple */}
      {data && data.length > 1 && (
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="track-booking" className="text-xs font-semibold text-zinc-500">
            {t("track.select")}
          </label>
          <select
            id="track-booking"
            className="rounded-2xl border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 font-semibold"
            value={String(bookingId)}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {data.map((b) => (
              <option key={b.id || b._id || b.booking_reference} value={b.id || b._id || b.booking_reference}>
                {b.booking_reference || b.booking_id} · {b.service_type_details?.name || b.serviceType} ({statusLabel(b.status)})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Handover OTP Notice Box for Customer */}
      {otpCode && !booking.handover_otp_verified && (
        <div className="rounded-3xl bg-zinc-900 p-6 text-center text-white dark:bg-white dark:text-zinc-900 space-y-2">
          <span className="text-xs uppercase font-bold tracking-widest text-brand-fg">{t("track.shareHandover")}</span>
          <p className="font-mono text-4xl font-black tracking-[0.4em]">{otpCode}</p>
          <p className="text-xs text-zinc-400 dark:text-zinc-600">{t("track.handoverHint")}</p>
        </div>
      )}

      {/* Delivery OTP: the customer gives it to the driver when the car comes back */}
      {deliveryOtp && currentStatus === "Out for Delivery" && (
        <div className="rounded-3xl bg-emerald-700 p-6 text-center text-white space-y-2">
          <span className="text-xs uppercase font-bold tracking-widest text-emerald-200">{t("track.shareDelivery")}</span>
          <p className="font-mono text-4xl font-black tracking-[0.4em]">{deliveryOtp}</p>
          <p className="text-xs text-emerald-100">{t("track.deliveryHint")}</p>
        </div>
      )}

      {/* Live Map / Driver GPS Route Card */}
      <div className="glass overflow-hidden rounded-3xl">
        <div className="flex flex-col gap-5 p-5 sm:p-6 lg:flex-row">
          <div className="min-w-0 flex-1">
            <LiveTrackingMap
              pickup={pickupPoint}
              hub={hubPoint}
              hubName={centerName}
              route={(trackingData?.driver_route as RoutePoint[] | undefined) ?? []}
              heading={driverHeading}
            />
          </div>

          <div className="flex w-full flex-col justify-between lg:w-72 lg:py-1">
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="rounded-full bg-brand/15 px-3 py-1 text-xs font-bold text-brand-fg">
                  {statusLabel(currentStatus)}
                </span>
              </div>
              <h2 className="mt-4 text-2xl font-extrabold">{refCode}</h2>
              <p className="mt-1 text-sm leading-6 text-zinc-500">{address}</p>

              <div className="mt-5 grid grid-cols-2 gap-2">
                <div className="rounded-2xl bg-zinc-100/80 p-3 dark:bg-zinc-800/70">
                  <Clock3 size={16} className="text-brand-fg" />
                  <p className="mt-2 text-lg font-extrabold">{isOnTheWay ? t("track.arriving") : t("track.active")}</p>
                  <p className="text-xs text-zinc-500">{t("track.stage")}</p>
                </div>
                <div className="rounded-2xl bg-zinc-100/80 p-3 dark:bg-zinc-800/70">
                  <Navigation size={16} className="text-brand-fg" />
                  <p className="mt-2 text-lg font-extrabold">{driver ? t("track.assigned") : t("track.queued")}</p>
                  <p className="text-xs text-zinc-500">{t("track.valetAssignment")}</p>
                </div>
              </div>
            </div>

            <div className="mt-5 border-t border-zinc-200/70 pt-4 dark:border-zinc-700/70">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-zinc-400">{t("track.hub")}</p>
              <p className="mt-1 flex items-center gap-2 text-sm font-semibold">
                <Route size={15} className="text-brand-fg" /> {centerName}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Booking Details & Staff Info Card */}
      <div className="glass rounded-3xl p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200/70 pb-4 dark:border-zinc-700/70">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-brand-fg">{refCode}</span>
            <h2 className="text-2xl font-extrabold">{serviceName}</h2>
            <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {vehicleName} {regNumber ? `(${regNumber})` : ""}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-400">{t("track.cost")}</p>
            <p className="text-2xl font-black text-emerald-600">
              ₹{Number(cost).toLocaleString("en-IN")}
            </p>
          </div>
        </div>

        {/* Driver & Mechanic Staff Badges */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="rounded-2xl bg-zinc-100/70 p-3 dark:bg-zinc-800/70">
            <span className="text-zinc-400 font-bold uppercase block mb-0.5">{t("track.valet")}</span>
            <p className="font-bold text-sm text-zinc-800 dark:text-zinc-100">
              {driver ? (driver.name || driver.email) : t("track.unassigned")}
            </p>
            {driver?.phone && <p className="text-zinc-500 font-mono mt-0.5">Phone: {driver.phone}</p>}
          </div>

          <div className="rounded-2xl bg-zinc-100/70 p-3 dark:bg-zinc-800/70">
            <span className="text-zinc-400 font-bold uppercase block mb-0.5">{t("track.mechanic")}</span>
            <p className="font-bold text-sm text-zinc-800 dark:text-zinc-100">
              {mechanic ? (mechanic.name || mechanic.email) : t("track.unassigned")}
            </p>
          </div>
        </div>

        {/* Action Controls & Cancellation Button */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex gap-2">
            <RouterLink className="rounded-2xl bg-brand px-4 py-2 text-sm font-semibold text-white" to="/app/approvals">
              {t("track.approvals")}
            </RouterLink>
          </div>

          {/* Cancellation Button */}
          {isCancellable ? (
            <button
              onClick={handleCancelBooking}
              disabled={cancelling}
              className="flex items-center gap-1.5 rounded-2xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-bold text-red-600 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400 disabled:opacity-50"
            >
              <XCircle size={16} />
              {cancelling ? t("track.cancelling") : t("track.cancel")}
            </button>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-zinc-500 italic">
              <AlertTriangle size={14} className="text-amber-500" />
              <span>{t("track.cannotCancel")}</span>
            </div>
          )}
        </div>
      </div>

      {currentStatus === "Completed" && !booking.has_review && (
        <ReviewForm bookingId={booking.id} hasDriver={!!booking.assigned_driver} onDone={reload} />
      )}

      {bookingId && <ConditionReportView key={String(bookingId)} bookingId={bookingId} />}

      {/* Visual Timeline Tracker */}
      <div className="glass rounded-3xl p-6">
        <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400 mb-4">{t("track.timeline")}</h3>
        {STEPS.map((s, i) => {
          const stepDone = currentStepIdx >= 0 && i <= currentStepIdx;
          const isCurrent = currentStepIdx >= 0 && i === currentStepIdx;

          return (
            <div key={s} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={`h-3.5 w-3.5 rounded-full ${
                    isCurrent
                      ? "bg-brand ring-4 ring-brand/20"
                      : stepDone
                      ? "bg-brand"
                      : "bg-zinc-300 dark:bg-zinc-700"
                  }`}
                />
                {i < STEPS.length - 1 && (
                  <span className={`h-6 w-0.5 ${stepDone ? "bg-brand" : "bg-zinc-200 dark:bg-zinc-800"}`} />
                )}
              </div>
              <p
                className={`pb-4 text-sm ${
                  isCurrent
                    ? "font-bold text-brand-fg"
                    : stepDone
                    ? "font-semibold text-zinc-700 dark:text-zinc-300"
                    : "text-zinc-400"
                }`}
              >
                {statusLabel(s)}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function History() {
  const { data, loading, reload } = useApi<Booking[]>("/api/bookings/");
  const { t } = useLanguage();
  const statusLabel = useStatusLabel();
  const done = data?.filter((b) => ["Delivered", "Cancelled", "Completed"].includes(b.status)) ?? [];

  if (loading) return <Skeleton className="h-40" />;
  if (!done.length) return <Empty title="No past service history" />;

  return (
    <div className="space-y-3">
      {done.map((b) => (
        <article key={b.id || b._id || b.booking_reference} className="glass rounded-3xl p-5 flex flex-wrap justify-between items-center gap-4">
          <div>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${b.status === "Cancelled" ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"}`}>
              {statusLabel(b.status)}
            </span>
            <h3 className="mt-2 text-lg font-bold">{b.service_type_details?.name || b.serviceType || "Service"}</h3>
            <p className="text-xs text-zinc-500">
              Ref: {b.booking_reference || b.booking_id} · {b.preferred_date || ""}
            </p>
          </div>
          <div className="text-right">
            <p className="text-lg font-black text-zinc-800 dark:text-zinc-100">
              ₹{Number(b.estimated_cost || b.estimatedCost || 0).toLocaleString("en-IN")}
            </p>
            {b.status === "Completed" && b.has_review && <p className="text-xs font-semibold text-amber-600">{t("review.reviewed")}</p>}
          </div>
          {b.status === "Completed" && !b.has_review && (
            <div className="w-full sm:w-80">
              <ReviewForm bookingId={b.id} hasDriver={!!b.assigned_driver} onDone={reload} />
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
