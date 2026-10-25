import { FormEvent, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, Calendar, Clock, MapPin, Wrench, Building2, Car, AlertCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { useLanguage } from "../hooks/useLanguage";
import { Skeleton } from "../components/States";
import { GoogleLocationPicker } from "../components/GoogleLocationPicker";
import type { Vehicle, ServiceType, ServiceCenter, Booking } from "../types";

const defaultTomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
const DEFAULT_DATE = defaultTomorrow.toISOString().split("T")[0];

const MAX_DATE = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];

interface SlotInfo {
  time: string;
  label: string;
  capacity: number;
  booked: number;
  available: number;
  is_full: boolean;
}

export function Book() {
  const { data: vehicles, loading: loadingVehicles } = useApi<Vehicle[]>("/api/vehicles/");
  const { data: serviceTypes, loading: loadingServices } = useApi<ServiceType[]>("/api/service-types/");
  const { data: serviceCenters, loading: loadingCenters } = useApi<ServiceCenter[]>("/api/service-centers/");

  const [params] = useSearchParams();
  const { push } = useToast();
  const { t } = useLanguage();

  const [selectedVehicleId, setSelectedVehicleId] = useState(params.get("vehicle") || "");
  const [selectedServiceTypeId, setSelectedServiceTypeId] = useState<number | string>("");
  const [selectedServiceCenterId, setSelectedServiceCenterId] = useState<number | string>("");
  const [pickupAddress, setPickupAddress] = useState("100 Feet Road, Indiranagar, Bengaluru");
  const [pickupLatitude, setPickupLatitude] = useState<number | null>(12.9784);
  const [pickupLongitude, setPickupLongitude] = useState<number | null>(77.6408);
  const [preferredDate, setPreferredDate] = useState(DEFAULT_DATE);
  const [preferredTime, setPreferredTime] = useState("");
  const [customerNotes, setCustomerNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmedBooking, setConfirmedBooking] = useState<Booking | null>(null);

  // Derived effective values
  const effectiveVehicleId = useMemo(() => {
    if (selectedVehicleId) return selectedVehicleId;
    return vehicles?.[0]?.id || vehicles?.[0]?._id || "";
  }, [selectedVehicleId, vehicles]);

  const effectiveServiceType = useMemo(() => {
    if (!serviceTypes?.length) return null;
    if (selectedServiceTypeId) {
      return serviceTypes.find((s) => String(s.id) === String(selectedServiceTypeId)) || serviceTypes[0];
    }
    return serviceTypes[0];
  }, [selectedServiceTypeId, serviceTypes]);

  const effectiveServiceCenter = useMemo(() => {
    if (!serviceCenters?.length) return null;
    if (selectedServiceCenterId) {
      return serviceCenters.find((c) => String(c.id) === String(selectedServiceCenterId)) || serviceCenters[0];
    }
    return serviceCenters[0];
  }, [selectedServiceCenterId, serviceCenters]);

  const { data: slotData, loading: loadingSlots } = useApi<{ slots: SlotInfo[] }>(
    effectiveServiceCenter && preferredDate ? `/api/service-centers/${effectiveServiceCenter.id}/slots/?date=${preferredDate}` : null
  );
  const slots = slotData?.slots ?? [];
  // A slot chosen earlier may have filled up or belong to another date; only keep it while it is open.
  const chosenSlot = slots.find((s) => s.time === preferredTime && !s.is_full);

  const selectedVehicleObj = useMemo(() => {
    return vehicles?.find((v) => String(v.id || v._id) === String(effectiveVehicleId));
  }, [effectiveVehicleId, vehicles]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!effectiveVehicleId) return push({ title: "Please select a vehicle", tone: "err" });
    if (!effectiveServiceType) return push({ title: "Please select a service type", tone: "err" });
    if (!effectiveServiceCenter) return push({ title: "Please select a service center", tone: "err" });
    if (!pickupAddress.trim()) return push({ title: "Pickup address is required", tone: "err" });
    if (!chosenSlot) return push({ title: t("book.pickSlot"), tone: "err" });

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        vehicle: effectiveVehicleId,
        service_type: effectiveServiceType.id,
        service_center: effectiveServiceCenter.id,
        pickup_address: pickupAddress,
        preferred_date: preferredDate,
        preferred_time: chosenSlot.time,
        customer_notes: customerNotes,
        estimated_cost: effectiveServiceType.base_price,
      };

      if (pickupLatitude !== null && pickupLongitude !== null) {
        payload.pickup_latitude = pickupLatitude;
        payload.pickup_longitude = pickupLongitude;
      }

      const res = await api<Booking>("/api/bookings/", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      push({ title: t("book.success") });
      setConfirmedBooking(res);
    } catch (err) {
      const errorMsg = err instanceof ApiError ? err.message : "Failed to create booking";
      push({ title: errorMsg, tone: "err" });
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingVehicles || loadingServices || loadingCenters) {
    return <Skeleton className="h-96" />;
  }

  if (!vehicles?.length) {
    return (
      <div className="glass mx-auto max-w-xl rounded-3xl p-8 text-center space-y-4">
        <Car size={48} className="mx-auto text-zinc-400" />
        <h2 className="text-xl font-bold">{t("book.noVehicles")}</h2>
        <p className="text-sm text-zinc-500">{t("book.noVehiclesHint")}</p>
        <Link to="/app/vehicles" className="inline-block rounded-2xl bg-[#ff4d2e] px-6 py-3 font-semibold text-white">
          {t("book.addVehicle")}
        </Link>
      </div>
    );
  }

  // Confirmation View Screen
  if (confirmedBooking) {
    return (
      <div className="glass mx-auto max-w-xl rounded-3xl p-8 space-y-6">
        <div className="text-center space-y-3">
          <CheckCircle2 size={56} className="mx-auto text-emerald-500" />
          <h2 className="text-2xl font-extrabold">{t("book.confirmed")}</h2>
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">{t("book.reference")}</p>
          <p className="text-xl font-black text-[#ff4d2e] bg-[#ff4d2e]/10 py-2 px-4 rounded-2xl inline-block font-mono">
            {confirmedBooking.booking_reference || confirmedBooking.booking_id}
          </p>
        </div>

        <div className="rounded-2xl border border-zinc-200/70 p-4 space-y-3 dark:border-zinc-800 text-sm">
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">{t("book.service")}</span>
            <span className="font-semibold">{effectiveServiceType?.name}</span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">{t("book.vehicleLabel")}</span>
            <span className="font-semibold">
              {selectedVehicleObj?.brand} {selectedVehicleObj?.model} ({selectedVehicleObj?.registration_number || selectedVehicleObj?.registration})
            </span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">{t("book.centerLabel")}</span>
            <span className="font-semibold">{effectiveServiceCenter?.name}</span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">{t("book.when")}</span>
            <span className="font-semibold">
              {confirmedBooking.preferred_date} · {chosenSlot?.label || confirmedBooking.preferred_time}
            </span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">{t("book.cost")}</span>
            <span className="font-bold text-emerald-600">₹{Number(confirmedBooking.estimated_cost || 0).toLocaleString("en-IN")}</span>
          </div>
          {confirmedBooking.pickup_latitude && confirmedBooking.pickup_longitude && (
            <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
              <span className="text-zinc-500">Coordinates</span>
              <span className="font-mono text-xs font-semibold">
                {confirmedBooking.pickup_latitude.toFixed(4)}, {confirmedBooking.pickup_longitude.toFixed(4)}
              </span>
            </div>
          )}
          <div className="pt-1">
            <span className="text-zinc-500 block mb-1">{t("book.address")}</span>
            <p className="font-medium text-zinc-700 dark:text-zinc-300">{confirmedBooking.pickup_address}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            onClick={() => setConfirmedBooking(null)}
            className="w-full rounded-2xl border border-zinc-200 py-3 font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
          >
            {t("book.another")}
          </button>
          <Link
            to="/app/track"
            className="w-full text-center rounded-2xl bg-[#ff4d2e] py-3 font-semibold text-white block"
          >
            {t("book.viewBookings")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form className="glass mx-auto max-w-2xl space-y-5 rounded-3xl p-6 sm:p-8" onSubmit={onSubmit}>
      <div>
        <h1 className="text-2xl font-extrabold">{t("book.title")}</h1>
        <p className="text-sm text-zinc-500">{t("book.subtitle")}</p>
      </div>

      {/* Select Vehicle */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <Car size={16} className="text-[#ff4d2e]" /> {t("book.vehicle")}
        </span>
        <select
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          value={effectiveVehicleId}
          onChange={(e) => setSelectedVehicleId(e.target.value)}
        >
          {vehicles.map((v) => (
            <option key={v.id || v._id} value={v.id || v._id}>
              {v.nickname ? `${v.nickname} (` : ""}{v.brand} {v.model}{v.nickname ? ")" : ""} · {v.registration_number || v.registration}
            </option>
          ))}
        </select>
      </label>

      {/* Select Service Type */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <Wrench size={16} className="text-[#ff4d2e]" /> {t("book.package")}
        </span>
        <select
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          value={effectiveServiceType?.id || ""}
          onChange={(e) => setSelectedServiceTypeId(e.target.value)}
        >
          {serviceTypes?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — ₹{Number(s.base_price).toLocaleString("en-IN")} ({s.estimated_duration})
            </option>
          ))}
        </select>
        {effectiveServiceType && (
          <p className="mt-1 text-xs text-zinc-500 italic">{effectiveServiceType.description}</p>
        )}
      </label>

      {/* Select Service Center */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <Building2 size={16} className="text-[#ff4d2e]" /> {t("book.center")}
        </span>
        <select
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          value={effectiveServiceCenter?.id || ""}
          onChange={(e) => setSelectedServiceCenterId(e.target.value)}
        >
          {serviceCenters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.review_count ? t("book.reviews", { rating: c.average_rating ?? "", n: c.review_count }) : t("book.newCenter")}) — {c.address}
            </option>
          ))}
        </select>
      </label>

      {/* Google Maps Location & Pickup Address Picker */}
      <div className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-2 text-zinc-700 dark:text-zinc-300 font-bold">
          <MapPin size={16} className="text-[#ff4d2e]" /> {t("book.location")}
        </span>
        <GoogleLocationPicker
          address={pickupAddress}
          latitude={pickupLatitude}
          longitude={pickupLongitude}
          selectedCenter={effectiveServiceCenter}
          serviceCenters={serviceCenters || []}
          onChange={(data) => {
            setPickupAddress(data.address);
            setPickupLatitude(data.latitude);
            setPickupLongitude(data.longitude);
          }}
        />
      </div>

      {/* Preferred Date & Time Slot */}
      <div className="space-y-3">
        <label className="block text-xs font-semibold text-zinc-500">
          <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
            <Calendar size={16} className="text-[#ff4d2e]" /> {t("book.date")}
          </span>
          <input
            type="date"
            className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={preferredDate}
            onChange={(e) => setPreferredDate(e.target.value)}
            min={new Date().toISOString().split("T")[0]}
            max={MAX_DATE}
            required
          />
        </label>

        <div className="text-xs font-semibold text-zinc-500">
          <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
            <Clock size={16} className="text-[#ff4d2e]" /> {t("book.slot")}
          </span>
          {loadingSlots ? (
            <Skeleton className="h-20" />
          ) : !slots.length ? (
            <p className="rounded-2xl bg-zinc-100 p-3 dark:bg-zinc-800/60">{t("book.slotsHint")}</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {slots.map((s) => {
                const selected = chosenSlot?.time === s.time;
                return (
                  <button
                    key={s.time}
                    type="button"
                    disabled={s.is_full}
                    onClick={() => setPreferredTime(s.time)}
                    className={`rounded-2xl border px-3 py-2.5 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${
                      selected
                        ? "border-[#ff4d2e] bg-[#ff4d2e]/10 text-[#ff4d2e]"
                        : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700"
                    }`}
                  >
                    <span className="block text-sm font-bold">{s.label}</span>
                    <span className={`text-[11px] ${s.is_full ? "text-red-500" : s.available === 1 ? "text-amber-600" : "text-emerald-600"}`}>
                      {s.is_full ? t("book.full") : t("book.placesLeft", { n: s.available, cap: s.capacity })}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Customer Notes */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <AlertCircle size={16} className="text-[#ff4d2e]" /> {t("book.notes")}
        </span>
        <textarea
          rows={2}
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder={t("book.notesPlaceholder")}
          value={customerNotes}
          onChange={(e) => setCustomerNotes(e.target.value)}
        />
      </label>

      {/* Price Estimation Preview Card */}
      {effectiveServiceType && (
        <div className="rounded-2xl bg-[#ff4d2e]/10 border border-[#ff4d2e]/20 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">{t("book.total")}</p>
            <p className="text-2xl font-black text-[#ff4d2e]">
              ₹{Number(effectiveServiceType.base_price).toLocaleString("en-IN")}
            </p>
            <p className="text-xs text-zinc-500">{t("book.includes")}</p>
          </div>
          <span className="rounded-xl bg-white dark:bg-zinc-900 px-3 py-1 text-xs font-semibold border border-zinc-200 dark:border-zinc-700">
            {effectiveServiceType.estimated_duration}
          </span>
        </div>
      )}

      <button
        disabled={submitting}
        className="w-full rounded-2xl bg-[#ff4d2e] py-3.5 font-bold text-white shadow-lg transition hover:bg-[#e03e21] disabled:opacity-50"
        type="submit"
      >
        {submitting ? t("book.submitting") : t("book.submit")}
      </button>
    </form>
  );
}
