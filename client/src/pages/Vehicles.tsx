import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Car, Plus, Trash2, Edit3, Eye, ShieldCheck, Fuel, Calendar, Wrench, X } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Empty, Skeleton } from "../components/States";
import { SearchableSelect } from "../components/SearchableSelect";
import type { Vehicle, CarBrand, CarModel, CarVariant } from "../types";

export function Vehicles() {
  const { data: vehicles, loading, error, reload } = useApi<Vehicle[]>("/api/vehicles/");
  const { push } = useToast();

  const [openModal, setOpenModal] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);
  const [viewingVehicle, setViewingVehicle] = useState<Vehicle | null>(null);

  // Catalog State
  const [brands, setBrands] = useState<CarBrand[]>([]);
  const [models, setModels] = useState<CarModel[]>([]);
  const [variants, setVariants] = useState<CarVariant[]>([]);

  const [loadingBrands, setLoadingBrands] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingVariants, setLoadingVariants] = useState(false);

  // Form State
  const [selectedBrandId, setSelectedBrandId] = useState<number | string>("");
  const [selectedModelId, setSelectedModelId] = useState<number | string>("");
  const [selectedVariantId, setSelectedVariantId] = useState<number | string>("");

  const [registrationNumber, setRegistrationNumber] = useState("");
  const [year, setYear] = useState<number>(2023);
  const [color, setColor] = useState("");
  const [odometer, setOdometer] = useState("");
  const [nickname, setNickname] = useState("");
  const [fuelType, setFuelType] = useState("Petrol");
  const [busy, setBusy] = useState(false);

  // Fetch Brands on Mount or Modal Open
  useEffect(() => {
    if (openModal) {
      setLoadingBrands(true);
      api<CarBrand[]>("/api/car-brands/")
        .then(setBrands)
        .catch(() => push({ title: "Failed to load car brands", tone: "err" }))
        .finally(() => setLoadingBrands(false));
    }
  }, [openModal]);

  // Fetch Models when Brand changes
  useEffect(() => {
    if (!selectedBrandId) {
      setModels([]);
      setSelectedModelId("");
      setVariants([]);
      setSelectedVariantId("");
      return;
    }
    setLoadingModels(true);
    api<CarModel[]>(`/api/car-brands/${selectedBrandId}/models/`)
      .then(setModels)
      .catch(() => push({ title: "Failed to load car models", tone: "err" }))
      .finally(() => setLoadingModels(false));
  }, [selectedBrandId]);

  // Fetch Variants when Model changes
  useEffect(() => {
    if (!selectedModelId) {
      setVariants([]);
      setSelectedVariantId("");
      return;
    }
    setLoadingVariants(true);
    api<CarVariant[]>(`/api/car-models/${selectedModelId}/variants/`)
      .then(setVariants)
      .catch(() => push({ title: "Failed to load car variants", tone: "err" }))
      .finally(() => setLoadingVariants(false));
  }, [selectedModelId]);

  // Auto-fill fuel type when Variant is selected
  const handleVariantChange = (id: number | string) => {
    setSelectedVariantId(id);
    const selectedVar = variants.find((v) => String(v.id) === String(id));
    if (selectedVar) {
      setFuelType(selectedVar.fuel_type);
    }
  };

  const handleOpenAdd = () => {
    setEditingVehicle(null);
    setSelectedBrandId("");
    setSelectedModelId("");
    setSelectedVariantId("");
    setRegistrationNumber("");
    setYear(2023);
    setColor("");
    setOdometer("");
    setNickname("");
    setFuelType("Petrol");
    setOpenModal(true);
  };

  const handleOpenEdit = (v: Vehicle) => {
    setEditingVehicle(v);
    setRegistrationNumber(v.registration_number || v.registration || "");
    setYear(v.year || 2021);
    setColor(v.color || "");
    setOdometer(v.odometer_km != null ? String(v.odometer_km) : "");
    setNickname(v.nickname || "");
    setFuelType(v.fuel_type || v.fuelType || "Petrol");

    if (v.car_brand) setSelectedBrandId(v.car_brand);
    if (v.car_model) setSelectedModelId(v.car_model);
    if (v.car_variant) setSelectedVariantId(v.car_variant);

    setOpenModal(true);
  };

  const handleDelete = async (id: number | string) => {
    if (!confirm("Are you sure you want to remove this vehicle from your garage?")) return;
    try {
      await api(`/api/vehicles/${id}/`, { method: "DELETE" });
      push({ title: "Vehicle removed successfully" });
      reload();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Failed to delete vehicle", tone: "err" });
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!registrationNumber.trim()) {
      push({ title: "Registration number is required", tone: "err" });
      return;
    }

    const selectedB = brands.find((b) => String(b.id) === String(selectedBrandId));
    const selectedM = models.find((m) => String(m.id) === String(selectedModelId));
    const selectedV = variants.find((v) => String(v.id) === String(selectedVariantId));

    setBusy(true);
    try {
      const payload: Record<string, any> = {
        registration_number: registrationNumber.trim().toUpperCase(),
        year: Number(year),
        color: color.trim(),
        odometer_km: odometer.trim() ? Number(odometer) : null,
        nickname: nickname.trim() || (selectedB && selectedM ? `${selectedB.name} ${selectedM.name}` : "My Car"),
        fuel_type: fuelType,
      };

      if (selectedBrandId) payload.car_brand_id = selectedBrandId;
      if (selectedModelId) payload.car_model_id = selectedModelId;
      if (selectedVariantId) payload.car_variant_id = selectedVariantId;

      if (selectedB) payload.brand = selectedB.name;
      if (selectedM) payload.model = selectedM.name;
      if (selectedV) payload.variant_name = selectedV.name;

      if (editingVehicle?.id) {
        await api(`/api/vehicles/${editingVehicle.id}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        push({ title: "Vehicle updated successfully!" });
      } else {
        await api("/api/vehicles/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        push({ title: "Vehicle added to your garage!" });
      }

      setOpenModal(false);
      reload();
    } catch (err) {
      push({
        title: err instanceof ApiError ? err.message : "Could not save vehicle",
        tone: "err",
      });
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Skeleton className="h-64" />;
  if (error) return <Empty title="Could not load vehicles" hint={error} />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold">My Garage</h1>
          <p className="text-sm text-zinc-500">Manage your registered vehicles and service history.</p>
        </div>
        <button
          type="button"
          onClick={handleOpenAdd}
          className="flex items-center gap-2 rounded-2xl bg-[#ff4d2e] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#e94529] shadow-lg shadow-[#ff4d2e]/20"
        >
          <Plus size={18} /> Add Vehicle
        </button>
      </div>

      {/* Vehicle Grid */}
      {!vehicles?.length ? (
        <Empty
          title="No vehicles in garage"
          hint="Select your vehicle brand, model and variant to book doorstep servicing."
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {vehicles.map((v) => {
            const reg = v.registration_number || v.registration;
            const bName = v.brand || v.car_brand_details?.name || "Vehicle";
            const mName = v.model || v.car_model_details?.name || "";
            const vName = v.variant_name || v.car_variant_details?.name || "";

            return (
              <div
                key={v.id || v._id}
                className="glass group relative overflow-hidden rounded-3xl p-6 transition duration-200 hover:-translate-y-1 hover:shadow-xl"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#ff4d2e]/10 text-[#ff4d2e]">
                      <Car size={24} />
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">{v.nickname || "My Car"}</p>
                      <h3 className="text-lg font-bold">{bName} {mName}</h3>
                    </div>
                  </div>
                  <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-bold text-emerald-600">
                    Active
                  </span>
                </div>

                <div className="mt-5 space-y-2 text-xs text-zinc-600 dark:text-zinc-400">
                  {vName && (
                    <div className="flex items-center justify-between border-b border-zinc-200/50 py-1.5 dark:border-zinc-800">
                      <span>Variant</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">{vName}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between border-b border-zinc-200/50 py-1.5 dark:border-zinc-800">
                    <span className="flex items-center gap-1.5"><ShieldCheck size={14} className="text-[#ff4d2e]" /> Reg. Number</span>
                    <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">{reg}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-zinc-200/50 py-1.5 dark:border-zinc-800">
                    <span className="flex items-center gap-1.5"><Calendar size={14} /> Model Year</span>
                    <span className="font-semibold">{v.year}</span>
                  </div>
                  <div className="flex items-center justify-between py-1.5">
                    <span className="flex items-center gap-1.5"><Fuel size={14} /> Fuel Type</span>
                    <span className="font-semibold">{v.fuel_type || v.fuelType}</span>
                  </div>
                </div>

                <div className="mt-6 flex items-center gap-2 border-t border-zinc-200/70 pt-4 dark:border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setViewingVehicle(v)}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-zinc-200 py-2 text-xs font-semibold hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                  >
                    <Eye size={14} /> View
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenEdit(v)}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-zinc-200 py-2 text-xs font-semibold hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                  >
                    <Edit3 size={14} /> Edit
                  </button>
                  <Link
                    to={`/app/book?vehicle=${v.id || v._id}`}
                    className="flex flex-1 items-center justify-center gap-1 rounded-xl bg-[#ff4d2e] py-2 text-xs font-bold text-white transition hover:bg-[#e94529]"
                  >
                    <Wrench size={13} /> Book
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(v.id || v._id || "")}
                    className="p-2 text-zinc-400 hover:text-red-500 transition"
                    title="Delete vehicle"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add / Edit Vehicle Modal */}
      {openModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center justify-between border-b border-zinc-200/70 pb-4 dark:border-zinc-800">
              <h2 className="text-xl font-bold">
                {editingVehicle ? "Edit Vehicle Details" : "Add Vehicle to Garage"}
              </h2>
              <button
                type="button"
                onClick={() => setOpenModal(false)}
                className="rounded-full p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800"
              >
                <X size={20} />
              </button>
            </div>

            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              {/* 1. Cascading Brand Dropdown */}
              <SearchableSelect
                label="1. Select Car Brand"
                placeholder="Search brand (e.g. Maruti, BMW, Hyundai)..."
                options={brands.map((b) => ({ id: b.id, name: b.name }))}
                value={selectedBrandId}
                onChange={(id) => {
                  setSelectedBrandId(id);
                  setSelectedModelId("");
                  setSelectedVariantId("");
                }}
                loading={loadingBrands}
              />

              {/* 2. Cascading Model Dropdown */}
              <SearchableSelect
                label="2. Select Car Model"
                placeholder={selectedBrandId ? "Search model..." : "Select brand first"}
                options={models.map((m) => ({ id: m.id, name: m.name, sublabel: m.body_type }))}
                value={selectedModelId}
                onChange={(id) => {
                  setSelectedModelId(id);
                  setSelectedVariantId("");
                }}
                disabled={!selectedBrandId}
                loading={loadingModels}
                emptyText="No models found for this brand"
              />

              {/* 3. Cascading Variant Dropdown */}
              <SearchableSelect
                label="3. Select Variant"
                placeholder={selectedModelId ? "Search variant..." : "Select model first"}
                options={variants.map((v) => ({
                  id: v.id,
                  name: v.name,
                  sublabel: `${v.fuel_type} · ${v.transmission}`,
                }))}
                value={selectedVariantId}
                onChange={handleVariantChange}
                disabled={!selectedModelId}
                loading={loadingVariants}
                emptyText="No variants found for this model"
              />

              {/* 4. Registration Number & Year */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    Registration Number *
                  </label>
                  <input
                    required
                    className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 font-mono text-sm font-bold tracking-wider dark:border-zinc-700 dark:bg-zinc-900"
                    placeholder="KA 01 AB 1234"
                    value={registrationNumber}
                    onChange={(e) => setRegistrationNumber(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    Manufacturing Year
                  </label>
                  <select
                    className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                  >
                    {Array.from({ length: 17 }, (_, i) => 2026 - i).map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="vehicle-odometer" className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                  Current Odometer (km, optional)
                </label>
                <input
                  id="vehicle-odometer"
                  type="number"
                  min={0}
                  inputMode="numeric"
                  className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  placeholder="e.g. 32500 — used for service reminders"
                  value={odometer}
                  onChange={(e) => setOdometer(e.target.value)}
                />
              </div>

              {/* Fuel Type & Nickname */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    Fuel Type
                  </label>
                  <select
                    className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    value={fuelType}
                    onChange={(e) => setFuelType(e.target.value)}
                  >
                    {["Petrol", "Diesel", "CNG", "Electric", "Hybrid"].map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    Nickname (Optional)
                  </label>
                  <input
                    className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    placeholder="e.g. My Black Beauty"
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                  />
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-3 border-t border-zinc-200/70 pt-4 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setOpenModal(false)}
                  className="rounded-2xl border border-zinc-200 px-4 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  Cancel
                </button>
                <button
                  disabled={busy}
                  type="submit"
                  className="rounded-2xl bg-[#ff4d2e] px-6 py-2.5 text-xs font-bold text-white transition hover:bg-[#e94529] disabled:opacity-50"
                >
                  {busy ? "Saving..." : editingVehicle ? "Save Changes" : "Save Vehicle"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Vehicle Detail View Modal */}
      {viewingVehicle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-md overflow-hidden rounded-3xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center justify-between border-b border-zinc-200/70 pb-3 dark:border-zinc-800">
              <h2 className="text-xl font-bold">Vehicle Details</h2>
              <button
                type="button"
                onClick={() => setViewingVehicle(null)}
                className="rounded-full p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800"
              >
                <X size={20} />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                <span className="text-zinc-500">Brand</span>
                <span className="font-bold">{viewingVehicle.brand || viewingVehicle.car_brand_details?.name}</span>
              </div>
              <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                <span className="text-zinc-500">Model</span>
                <span className="font-bold">{viewingVehicle.model || viewingVehicle.car_model_details?.name}</span>
              </div>
              {viewingVehicle.variant_name && (
                <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                  <span className="text-zinc-500">Variant</span>
                  <span className="font-bold">{viewingVehicle.variant_name}</span>
                </div>
              )}
              <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                <span className="text-zinc-500">Registration</span>
                <span className="font-mono font-bold">{viewingVehicle.registration_number || viewingVehicle.registration}</span>
              </div>
              <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                <span className="text-zinc-500">Manufacturing Year</span>
                <span className="font-bold">{viewingVehicle.year}</span>
              </div>
              <div className="flex justify-between border-b py-2 dark:border-zinc-800">
                <span className="text-zinc-500">Odometer</span>
                <span className="font-bold">{viewingVehicle.odometer_km != null ? `${viewingVehicle.odometer_km.toLocaleString("en-IN")} km` : "Not recorded"}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-zinc-500">Fuel Type</span>
                <span className="font-bold">{viewingVehicle.fuel_type || viewingVehicle.fuelType}</span>
              </div>
            </div>

            <div className="mt-6">
              <button
                type="button"
                onClick={() => setViewingVehicle(null)}
                className="w-full rounded-2xl bg-zinc-900 py-2.5 text-xs font-semibold text-white dark:bg-white dark:text-zinc-900"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
