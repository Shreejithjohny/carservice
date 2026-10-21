import { FormEvent, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, Calendar, Clock, MapPin, Wrench, Building2, Car, AlertCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton } from "../components/States";
import { GoogleLocationPicker } from "../components/GoogleLocationPicker";
import type { Vehicle, ServiceType, ServiceCenter, Booking } from "../types";

const defaultTomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
const DEFAULT_DATE = defaultTomorrow.toISOString().split("T")[0];

const TIME_SLOTS = [
  { value: "09:00:00", label: "09:00 AM - 11:00 AM" },
  { value: "11:00:00", label: "11:00 AM - 01:00 PM" },
  { value: "14:00:00", label: "02:00 PM - 04:00 PM" },
  { value: "16:00:00", label: "04:00 PM - 06:00 PM" },
];

export function Book() {
  const { data: vehicles, loading: loadingVehicles } = useApi<Vehicle[]>("/api/vehicles/");
  const { data: serviceTypes, loading: loadingServices } = useApi<ServiceType[]>("/api/service-types/");
  const { data: serviceCenters, loading: loadingCenters } = useApi<ServiceCenter[]>("/api/service-centers/");

  const [params] = useSearchParams();
  const { push } = useToast();

  const [selectedVehicleId, setSelectedVehicleId] = useState(params.get("vehicle") || "");
  const [selectedServiceTypeId, setSelectedServiceTypeId] = useState<number | string>("");
  const [selectedServiceCenterId, setSelectedServiceCenterId] = useState<number | string>("");
  const [pickupAddress, setPickupAddress] = useState("100 Feet Road, Indiranagar, Bengaluru");
  const [pickupLatitude, setPickupLatitude] = useState<number | null>(12.9784);
  const [pickupLongitude, setPickupLongitude] = useState<number | null>(77.6408);
  const [preferredDate, setPreferredDate] = useState(DEFAULT_DATE);
  const [preferredTime, setPreferredTime] = useState("10:00:00");
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

  const selectedVehicleObj = useMemo(() => {
    return vehicles?.find((v) => String(v.id || v._id) === String(effectiveVehicleId));
  }, [effectiveVehicleId, vehicles]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!effectiveVehicleId) return push({ title: "Please select a vehicle", tone: "err" });
    if (!effectiveServiceType) return push({ title: "Please select a service type", tone: "err" });
    if (!effectiveServiceCenter) return push({ title: "Please select a service center", tone: "err" });
    if (!pickupAddress.trim()) return push({ title: "Pickup address is required", tone: "err" });

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        vehicle: effectiveVehicleId,
        service_type: effectiveServiceType.id,
        service_center: effectiveServiceCenter.id,
        pickup_address: pickupAddress,
        preferred_date: preferredDate,
        preferred_time: preferredTime,
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

      push({ title: "Booking confirmed successfully!" });
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
        <h2 className="text-xl font-bold">No Vehicles Found</h2>
        <p className="text-sm text-zinc-500">You need to register at least one vehicle before booking a doorstep service.</p>
        <Link to="/app/vehicles" className="inline-block rounded-2xl bg-[#ff4d2e] px-6 py-3 font-semibold text-white">
          Add New Vehicle
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
          <h2 className="text-2xl font-extrabold">Booking Confirmed!</h2>
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Booking Reference</p>
          <p className="text-xl font-black text-[#ff4d2e] bg-[#ff4d2e]/10 py-2 px-4 rounded-2xl inline-block font-mono">
            {confirmedBooking.booking_reference || confirmedBooking.booking_id}
          </p>
        </div>

        <div className="rounded-2xl border border-zinc-200/70 p-4 space-y-3 dark:border-zinc-800 text-sm">
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Service</span>
            <span className="font-semibold">{effectiveServiceType?.name}</span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Vehicle</span>
            <span className="font-semibold">
              {selectedVehicleObj?.brand} {selectedVehicleObj?.model} ({selectedVehicleObj?.registration_number || selectedVehicleObj?.registration})
            </span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Service Center</span>
            <span className="font-semibold">{effectiveServiceCenter?.name}</span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Pickup Date & Time</span>
            <span className="font-semibold">
              {confirmedBooking.preferred_date} at {confirmedBooking.preferred_time}
            </span>
          </div>
          <div className="flex justify-between items-center pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <span className="text-zinc-500">Estimated Cost</span>
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
            <span className="text-zinc-500 block mb-1">Pickup Address</span>
            <p className="font-medium text-zinc-700 dark:text-zinc-300">{confirmedBooking.pickup_address}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <button
            onClick={() => setConfirmedBooking(null)}
            className="w-full rounded-2xl border border-zinc-200 py-3 font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
          >
            Book Another
          </button>
          <Link
            to="/app/track"
            className="w-full text-center rounded-2xl bg-[#ff4d2e] py-3 font-semibold text-white block"
          >
            View My Bookings
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form className="glass mx-auto max-w-2xl space-y-5 rounded-3xl p-6 sm:p-8" onSubmit={onSubmit}>
      <div>
        <h1 className="text-2xl font-extrabold">Book Doorstep Service</h1>
        <p className="text-sm text-zinc-500">Select your vehicle, location on Google Maps, and preferred pickup slot.</p>
      </div>

      {/* Select Vehicle */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <Car size={16} className="text-[#ff4d2e]" /> Select Vehicle
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
          <Wrench size={16} className="text-[#ff4d2e]" /> Select Service Package
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
          <Building2 size={16} className="text-[#ff4d2e]" /> Preferred Service Center
        </span>
        <select
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          value={effectiveServiceCenter?.id || ""}
          onChange={(e) => setSelectedServiceCenterId(e.target.value)}
        >
          {serviceCenters?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.address})
            </option>
          ))}
        </select>
      </label>

      {/* Google Maps Location & Pickup Address Picker */}
      <div className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-2 text-zinc-700 dark:text-zinc-300 font-bold">
          <MapPin size={16} className="text-[#ff4d2e]" /> Doorstep Pickup Location
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

      {/* Preferred Date & Time */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="block text-xs font-semibold text-zinc-500">
          <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
            <Calendar size={16} className="text-[#ff4d2e]" /> Pickup Date
          </span>
          <input
            type="date"
            className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={preferredDate}
            onChange={(e) => setPreferredDate(e.target.value)}
            min={new Date().toISOString().split("T")[0]}
            required
          />
        </label>

        <label className="block text-xs font-semibold text-zinc-500">
          <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
            <Clock size={16} className="text-[#ff4d2e]" /> Time Slot
          </span>
          <select
            className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={preferredTime}
            onChange={(e) => setPreferredTime(e.target.value)}
          >
            {TIME_SLOTS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Customer Notes */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-1.5 mb-1.5 text-zinc-700 dark:text-zinc-300 font-bold">
          <AlertCircle size={16} className="text-[#ff4d2e]" /> Additional Requirements / Notes (Optional)
        </span>
        <textarea
          rows={2}
          className="w-full rounded-2xl border border-zinc-200 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="e.g. Check AC noise, check front left tire pressure"
          value={customerNotes}
          onChange={(e) => setCustomerNotes(e.target.value)}
        />
      </label>

      {/* Price Estimation Preview Card */}
      {effectiveServiceType && (
        <div className="rounded-2xl bg-[#ff4d2e]/10 border border-[#ff4d2e]/20 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">Estimated Total Cost</p>
            <p className="text-2xl font-black text-[#ff4d2e]">
              ₹{Number(effectiveServiceType.base_price).toLocaleString("en-IN")}
            </p>
            <p className="text-xs text-zinc-500">Includes free doorstep pickup & delivery</p>
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
        {submitting ? "Processing Booking..." : "Confirm & Schedule Service"}
      </button>
    </form>
  );
}
