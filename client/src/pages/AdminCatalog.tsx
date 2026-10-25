import { FormEvent, useEffect, useState } from "react";
import { Plus, CheckCircle, XCircle, Search, RefreshCw } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useToast } from "../hooks/useToast";
import { Skeleton } from "../components/States";
import type { CarBrand, CarModel, CarVariant } from "../types";

export function AdminCatalog() {
  const { push } = useToast();
  const [activeTab, setActiveTab] = useState<"brands" | "models" | "variants">("brands");

  const [brands, setBrands] = useState<CarBrand[]>([]);
  const [models, setModels] = useState<CarModel[]>([]);
  const [variants, setVariants] = useState<CarVariant[]>([]);

  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // New item form states
  const [newBrandName, setNewBrandName] = useState("");
  const [newModelName, setNewModelName] = useState("");
  const [newModelBrandId, setNewModelBrandId] = useState<number | string>("");
  const [newModelBodyType, setNewModelBodyType] = useState("Hatchback");

  const [newVariantName, setNewVariantName] = useState("");
  const [newVariantModelId, setNewVariantModelId] = useState<number | string>("");
  const [newVariantFuel, setNewVariantFuel] = useState("Petrol");
  const [newVariantTransmission, setNewVariantTransmission] = useState("Manual");

  const [busy, setBusy] = useState(false);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const [bRes, mRes, vRes] = await Promise.all([
        api<CarBrand[]>("/api/car-brands/"),
        api<CarModel[]>("/api/car-models/"),
        api<CarVariant[]>("/api/car-variants/"),
      ]);
      setBrands(bRes);
      setModels(mRes);
      setVariants(vRes);
    } catch {
      push({ title: "Failed to load catalog data", tone: "err" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAllData();
  }, []);

  const handleAddBrand = async (e: FormEvent) => {
    e.preventDefault();
    if (!newBrandName.trim()) return;
    setBusy(true);
    try {
      await api("/api/car-brands/", {
        method: "POST",
        body: JSON.stringify({ name: newBrandName.trim() }),
      });
      push({ title: `Brand "${newBrandName}" created successfully` });
      setNewBrandName("");
      loadAllData();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Failed to add brand", tone: "err" });
    } finally {
      setBusy(false);
    }
  };

  const handleAddModel = async (e: FormEvent) => {
    e.preventDefault();
    if (!newModelName.trim() || !newModelBrandId) return;
    setBusy(true);
    try {
      await api("/api/car-models/", {
        method: "POST",
        body: JSON.stringify({
          brand: Number(newModelBrandId),
          name: newModelName.trim(),
          body_type: newModelBodyType,
        }),
      });
      push({ title: `Model "${newModelName}" added successfully` });
      setNewModelName("");
      loadAllData();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Failed to add model", tone: "err" });
    } finally {
      setBusy(false);
    }
  };

  const handleAddVariant = async (e: FormEvent) => {
    e.preventDefault();
    if (!newVariantName.trim() || !newVariantModelId) return;
    setBusy(true);
    try {
      await api("/api/car-variants/", {
        method: "POST",
        body: JSON.stringify({
          model: Number(newVariantModelId),
          name: newVariantName.trim(),
          fuel_type: newVariantFuel,
          transmission: newVariantTransmission,
        }),
      });
      push({ title: `Variant "${newVariantName}" added successfully` });
      setNewVariantName("");
      loadAllData();
    } catch (err) {
      push({ title: err instanceof ApiError ? err.message : "Failed to add variant", tone: "err" });
    } finally {
      setBusy(false);
    }
  };

  const toggleBrandActive = async (brand: CarBrand) => {
    try {
      await api(`/api/car-brands/${brand.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !brand.is_active }),
      });
      push({ title: `Brand ${brand.name} ${!brand.is_active ? "activated" : "deactivated"}` });
      loadAllData();
    } catch {
      push({ title: "Failed to update brand status", tone: "err" });
    }
  };

  if (loading) return <Skeleton className="h-64" />;

  const filteredBrands = brands.filter((b) => b.name.toLowerCase().includes(search.toLowerCase()));
  const filteredModels = models.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.brand_name && m.brand_name.toLowerCase().includes(search.toLowerCase()))
  );
  const filteredVariants = variants.filter(
    (v) =>
      v.name.toLowerCase().includes(search.toLowerCase()) ||
      (v.model_name && v.model_name.toLowerCase().includes(search.toLowerCase())) ||
      (v.brand_name && v.brand_name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold">Vehicle Catalog Management</h1>
          <p className="text-sm text-zinc-500">Manage Indian passenger car brands, models, and variants.</p>
        </div>
        <button
          type="button"
          onClick={loadAllData}
          className="flex items-center gap-1.5 rounded-2xl border border-zinc-200 px-3 py-2 text-xs font-semibold hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          <RefreshCw size={14} /> Refresh Catalog
        </button>
      </div>

      {/* Navigation Tabs */}
      <div className="flex gap-2 border-b border-zinc-200 dark:border-zinc-800">
        <button
          type="button"
          onClick={() => setActiveTab("brands")}
          className={`pb-3 px-4 text-sm font-bold transition border-b-2 ${
            activeTab === "brands"
              ? "border-brand text-brand-fg"
              : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          }`}
        >
          Car Brands ({brands.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("models")}
          className={`pb-3 px-4 text-sm font-bold transition border-b-2 ${
            activeTab === "models"
              ? "border-brand text-brand-fg"
              : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          }`}
        >
          Car Models ({models.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("variants")}
          className={`pb-3 px-4 text-sm font-bold transition border-b-2 ${
            activeTab === "variants"
              ? "border-brand text-brand-fg"
              : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          }`}
        >
          Car Variants ({variants.length})
        </button>
      </div>

      {/* Search Input */}
      <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900">
        <Search size={16} className="text-zinc-400" />
        <input
          className="w-full bg-transparent text-sm outline-none"
          placeholder={`Search ${activeTab}...`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* TAB 1: BRANDS */}
      {activeTab === "brands" && (
        <div className="space-y-4">
          <form className="glass flex flex-wrap gap-3 rounded-3xl p-4" onSubmit={handleAddBrand}>
            <input
              required
              className="flex-1 rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="New Brand Name (e.g. Genesis)"
              value={newBrandName}
              onChange={(e) => setNewBrandName(e.target.value)}
            />
            <button
              disabled={busy}
              type="submit"
              className="flex items-center gap-1.5 rounded-2xl bg-brand px-4 py-2 text-xs font-bold text-white transition hover:bg-brand-hover disabled:opacity-50"
            >
              <Plus size={16} /> Add Brand
            </button>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {filteredBrands.map((b) => (
              <div key={b.id} className="glass flex items-center justify-between rounded-2xl p-4">
                <div>
                  <h3 className="font-bold">{b.name}</h3>
                  <p className="text-xs text-zinc-500">{b.models_count || 0} models</p>
                </div>
                <button
                  type="button"
                  onClick={() => toggleBrandActive(b)}
                  className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                    b.is_active ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-600"
                  }`}
                >
                  {b.is_active ? <CheckCircle size={12} /> : <XCircle size={12} />}
                  {b.is_active ? "Active" : "Inactive"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: MODELS */}
      {activeTab === "models" && (
        <div className="space-y-4">
          <form className="glass grid gap-3 rounded-3xl p-4 sm:grid-cols-4" onSubmit={handleAddModel}>
            <select
              required
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={newModelBrandId}
              onChange={(e) => setNewModelBrandId(e.target.value)}
            >
              <option value="">Select Brand *</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>

            <input
              required
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="Model Name (e.g. Swift)"
              value={newModelName}
              onChange={(e) => setNewModelName(e.target.value)}
            />

            <select
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={newModelBodyType}
              onChange={(e) => setNewModelBodyType(e.target.value)}
            >
              {["Hatchback", "Sedan", "SUV", "MUV", "Coupe", "Convertible", "EV"].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>

            <button
              disabled={busy}
              type="submit"
              className="flex items-center justify-center gap-1.5 rounded-2xl bg-brand px-4 py-2 text-xs font-bold text-white transition hover:bg-brand-hover disabled:opacity-50"
            >
              <Plus size={16} /> Add Model
            </button>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {filteredModels.map((m) => (
              <div key={m.id} className="glass flex items-center justify-between rounded-2xl p-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{m.brand_name}</p>
                  <h3 className="font-bold">{m.name}</h3>
                  <p className="text-xs text-zinc-500">{m.body_type} · {m.variants_count || 0} variants</p>
                </div>
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold text-emerald-600">
                  Active
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: VARIANTS */}
      {activeTab === "variants" && (
        <div className="space-y-4">
          <form className="glass grid gap-3 rounded-3xl p-4 sm:grid-cols-5" onSubmit={handleAddVariant}>
            <select
              required
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={newVariantModelId}
              onChange={(e) => setNewVariantModelId(e.target.value)}
            >
              <option value="">Select Model *</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.brand_name} {m.name}
                </option>
              ))}
            </select>

            <input
              required
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="Variant Name (e.g. ZXi+)"
              value={newVariantName}
              onChange={(e) => setNewVariantName(e.target.value)}
            />

            <select
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={newVariantFuel}
              onChange={(e) => setNewVariantFuel(e.target.value)}
            >
              {["Petrol", "Diesel", "CNG", "Electric", "Hybrid"].map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>

            <select
              className="rounded-2xl border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              value={newVariantTransmission}
              onChange={(e) => setNewVariantTransmission(e.target.value)}
            >
              {["Manual", "Automatic", "AMT", "CVT", "DCT"].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>

            <button
              disabled={busy}
              type="submit"
              className="flex items-center justify-center gap-1.5 rounded-2xl bg-brand px-4 py-2 text-xs font-bold text-white transition hover:bg-brand-hover disabled:opacity-50"
            >
              <Plus size={16} /> Add Variant
            </button>
          </form>

          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {filteredVariants.map((v) => (
              <div key={v.id} className="glass flex items-center justify-between rounded-2xl p-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                    {v.brand_name} {v.model_name}
                  </p>
                  <h3 className="font-bold">{v.name}</h3>
                  <p className="text-xs text-zinc-500">{v.fuel_type} · {v.transmission}</p>
                </div>
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold text-emerald-600">
                  Active
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
