import { useEffect, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { Clock, Crosshair, LoaderCircle, MapPin, Route, Search } from "lucide-react";
import { api, ApiError } from "../services/api";
import { BENGALURU_PRESETS, drivingMinutes, haversineKm } from "../utils/geo";
import type { ServiceCenter } from "../types";

const DEFAULT: [number, number] = [12.9716, 77.5946]; // Bengaluru centre

type Place = { label: string; latitude: number; longitude: number };

// Plain HTML markers (Leaflet's default image icons break under Vite bundling)
const PICKUP_ICON = L.divIcon({ className: "", html: '<div class="map-pin map-pin-pickup">P</div>', iconSize: [30, 30], iconAnchor: [15, 15] });
const HUB_ICON = L.divIcon({ className: "", html: '<div class="map-pin map-pin-hub">H</div>', iconSize: [30, 30], iconAnchor: [15, 15] });
const OTHER_HUB_ICON = L.divIcon({ className: "", html: '<div class="map-pin map-pin-hub map-pin-sm">H</div>', iconSize: [18, 18], iconAnchor: [9, 9] });

/** Moves the map to the pin whenever it is set from outside the map (search, preset, GPS). */
function FollowPin({ point, moveKey }: Readonly<{ point: [number, number]; moveKey: number }>) {
  const map = useMap();
  useEffect(() => {
    map.setView(point, Math.max(map.getZoom(), 15));
    // Only on moveKey: following every pin change would also re-center on the customer's own taps
  }, [map, moveKey]);
  return null;
}

function TapToPlace({ onPick }: Readonly<{ onPick: (lat: number, lng: number) => void }>) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

/**
 * Pickup location picker on a free OpenStreetMap map (no API key). Customers can tap the map, drag
 * the pin, search for a place, use their phone's location or tap a preset area. Address search
 * goes through our backend, which follows OpenStreetMap's usage rules.
 */
export function OsmLocationPicker({
  address,
  latitude,
  longitude,
  selectedCenter,
  serviceCenters,
  onChange,
}: Readonly<{
  address: string;
  latitude: number | null;
  longitude: number | null;
  selectedCenter: ServiceCenter | null;
  serviceCenters: ServiceCenter[];
  onChange: (data: { address: string; latitude: number; longitude: number }) => void;
}>) {
  const point: [number, number] = latitude != null && longitude != null ? [latitude, longitude] : DEFAULT;
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [busy, setBusy] = useState<"search" | "address" | "gps" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [moveKey, setMoveKey] = useState(0);

  // Pin set on the map itself: keep the view, look up a readable address for it
  async function placeFromMap(lat: number, lng: number) {
    onChange({ address, latitude: lat, longitude: lng });
    setBusy("address");
    setNotice(null);
    try {
      const res = await api<{ address: string }>(`/api/location/reverse/?lat=${lat}&lng=${lng}`);
      if (res.address) onChange({ address: res.address, latitude: lat, longitude: lng });
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : "Couldn't look up that address. You can type it below.");
    } finally {
      setBusy(null);
    }
  }

  // Pin set from outside the map: move the map to it
  function placeAndShow(place: { address: string; latitude: number; longitude: number }) {
    onChange(place);
    setMoveKey((k) => k + 1);
  }

  async function search() {
    if (query.trim().length < 3) return setNotice("Type at least 3 characters to search.");
    setBusy("search");
    setNotice(null);
    try {
      const res = await api<{ results: Place[] }>(`/api/location/search/?q=${encodeURIComponent(query.trim())}`);
      setResults(res.results);
      if (!res.results.length) setNotice("No places found. Try a nearby landmark, or tap the map.");
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : "Search failed. Tap the map or pick a preset area instead.");
    } finally {
      setBusy(null);
    }
  }

  function useMyLocation() {
    if (!("geolocation" in navigator)) return setNotice("This browser can't share its location.");
    setBusy("gps");
    setNotice(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(null);
        setMoveKey((k) => k + 1);
        void placeFromMap(pos.coords.latitude, pos.coords.longitude);
      },
      () => {
        setBusy(null);
        setNotice("Location permission was denied. Tap the map or search instead.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  const centerPoint =
    selectedCenter?.latitude != null && selectedCenter?.longitude != null ? ([selectedCenter.latitude, selectedCenter.longitude] as [number, number]) : null;
  const km = centerPoint ? haversineKm(point[0], point[1], centerPoint[0], centerPoint[1]) : null;

  return (
    <div className="space-y-3">
      {/* Search (a button, not a nested form: this sits inside the booking form) */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-3 text-zinc-400" />
          <input
            type="text"
            aria-label="Search for a place"
            className="w-full rounded-2xl border border-zinc-200 bg-white py-2.5 pl-10 pr-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="Search area, street or landmark"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void search();
              }
            }}
          />
        </div>
        <button
          type="button"
          onClick={() => void search()}
          disabled={busy !== null}
          className="rounded-2xl bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
        >
          {busy === "search" ? <LoaderCircle size={16} className="animate-spin" /> : "Search"}
        </button>
      </div>

      {results.length > 0 && (
        <ul className="divide-y divide-zinc-100 overflow-hidden rounded-2xl border border-zinc-200 bg-white text-xs dark:divide-zinc-800 dark:border-zinc-700 dark:bg-zinc-900">
          {results.map((r) => (
            <li key={`${r.latitude},${r.longitude}`}>
              <button
                type="button"
                className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800"
                onClick={() => {
                  placeAndShow({ address: r.label, latitude: r.latitude, longitude: r.longitude });
                  setResults([]);
                }}
              >
                <MapPin size={14} className="mt-0.5 shrink-0 text-brand-fg" />
                {r.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Map */}
      <div className="relative overflow-hidden rounded-3xl border border-zinc-200 dark:border-zinc-700">
        <MapContainer center={point} zoom={14} scrollWheelZoom={false} className="h-64 w-full">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <FollowPin point={point} moveKey={moveKey} />
          <TapToPlace onPick={(lat, lng) => void placeFromMap(lat, lng)} />
          {serviceCenters.map((c) =>
            c.latitude != null && c.longitude != null ? (
              <Marker key={c.id} position={[c.latitude, c.longitude]} icon={c.id === selectedCenter?.id ? HUB_ICON : OTHER_HUB_ICON}>
                <Tooltip>{c.name}</Tooltip>
              </Marker>
            ) : null
          )}
          <Marker
            position={point}
            icon={PICKUP_ICON}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const ll = (e.target as L.Marker).getLatLng();
                void placeFromMap(ll.lat, ll.lng);
              },
            }}
          >
            <Tooltip>Your pickup point</Tooltip>
          </Marker>
        </MapContainer>
        <div className="pointer-events-none absolute right-3 top-3 z-[400] rounded-full bg-zinc-900/80 px-3 py-1 text-[11px] font-semibold text-white">
          Tap the map or drag P to set your pickup point
        </div>
        <button
          type="button"
          onClick={useMyLocation}
          disabled={busy !== null}
          className="absolute bottom-7 right-3 z-[400] flex items-center gap-1.5 rounded-xl bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 shadow disabled:opacity-60 dark:bg-zinc-900 dark:text-zinc-200"
        >
          {busy === "gps" ? <LoaderCircle size={14} className="animate-spin" /> : <Crosshair size={14} />} Use my location
        </button>
      </div>

      {notice && <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">{notice}</p>}

      {/* Address text stays editable: the pin finds the street; the customer adds flat or house details */}
      <label className="block text-xs font-semibold text-zinc-500">
        <span className="flex items-center gap-2">
          Pickup address (add flat / house number)
          {busy === "address" && <LoaderCircle size={12} className="animate-spin" />}
        </span>
        <textarea
          rows={2}
          className="mt-1 w-full rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          value={address}
          onChange={(e) => onChange({ address: e.target.value, latitude: point[0], longitude: point[1] })}
        />
      </label>

      <div className="flex flex-wrap gap-1.5">
        {BENGALURU_PRESETS.map((p) => (
          <button
            key={p.name}
            type="button"
            onClick={() => placeAndShow({ address: p.name, latitude: p.lat, longitude: p.lng })}
            className="rounded-xl border border-zinc-200 bg-white px-2.5 py-1 text-xs font-semibold text-zinc-700 hover:border-brand dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
          >
            {p.name.split(",")[0]}
          </button>
        ))}
      </div>

      {selectedCenter && km != null && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-zinc-200/80 bg-white p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900">
          <span className="font-semibold text-zinc-600 dark:text-zinc-400">To {selectedCenter.name} (straight line):</span>
          <span className="flex items-center gap-3 font-bold">
            <span className="flex items-center gap-1 text-brand-fg">
              <Route size={14} /> {km} km
            </span>
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <Clock size={14} /> ~{drivingMinutes(km)} mins
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
