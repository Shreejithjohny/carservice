import { useEffect, useRef, useState } from "react";
import { AttributionControl, Map as MapLibreMap, Marker, NavigationControl } from "maplibre-gl";
import { Clock, Crosshair, LoaderCircle, MapPin, Route, Search } from "lucide-react";
import { api, ApiError } from "../../services/api";
import { BENGALURU_PRESETS, drivingMinutes, haversineKm } from "../../utils/geo";
import type { ServiceCenter } from "../../types";
import { GPS_DOT_HTML, HUB_PIN_SMALL_SVG, HUB_PIN_SVG, MAP_STYLE_URL, PIN_SVG, markerElement, type LngLat } from "./setup";

const DEFAULT: LngLat = [77.5946, 12.9716]; // Bengaluru centre (MapLibre uses [lng, lat])

type Place = { label: string; latitude: number; longitude: number };
type Props = Readonly<{
  address: string;
  latitude: number | null;
  longitude: number | null;
  selectedCenter: ServiceCenter | null;
  serviceCenters: ServiceCenter[];
  onChange: (data: { address: string; latitude: number; longitude: number }) => void;
}>;

/**
 * Pickup point picker in the style of delivery apps: the pin stays in the middle and the customer
 * drags the map under it; when the map stops, the address under the pin is looked up. Also offers
 * search, the phone's location and preset areas. Free OpenFreeMap vector map, no API key.
 */
export default function MapLocationPicker({ address, latitude, longitude, selectedCenter, serviceCenters, onChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const gpsDot = useRef<Marker | null>(null);
  // The latest props for map event handlers, which are attached once
  const latest = useRef({ address, onChange });
  latest.current = { address, onChange };
  // Set before moving the map ourselves (search, preset), so that move does not trigger a lookup
  const skipNextLookup = useRef(false);
  const lookupId = useRef(0);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [busy, setBusy] = useState<"search" | "address" | "gps" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [moving, setMoving] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);

  const point: LngLat = latitude != null && longitude != null ? [longitude, latitude] : DEFAULT;

  async function lookUpAddress(lng: number, lat: number) {
    const id = ++lookupId.current;
    setBusy("address");
    setNotice(null);
    try {
      const res = await api<{ address: string }>(`/api/location/reverse/?lat=${lat}&lng=${lng}`);
      // Ignore answers that arrive after the customer has already moved the map again
      if (id === lookupId.current && res.address) latest.current.onChange({ address: res.address, latitude: lat, longitude: lng });
    } catch (err) {
      if (id === lookupId.current) setNotice(err instanceof ApiError ? err.message : "Couldn't look up that address. You can type it below.");
    } finally {
      if (id === lookupId.current) setBusy(null);
    }
  }

  // Create the map once
  useEffect(() => {
    if (!containerRef.current) return;
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({
        container: containerRef.current,
        style: MAP_STYLE_URL,
        center: point,
        zoom: 16,
        attributionControl: false,
        cooperativeGestures: false,
      });
    } catch {
      setMapFailed(true); // e.g. WebGL turned off in the browser
      return;
    }
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    map.addControl(new AttributionControl({ compact: true }), "bottom-left");
    map.on("dragstart", () => setDragging(true));
    map.on("movestart", () => setMoving(true));
    map.on("moveend", () => {
      setDragging(false);
      setMoving(false);
      if (skipNextLookup.current) {
        skipNextLookup.current = false;
        return;
      }
      const c = map.getCenter();
      latest.current.onChange({ address: latest.current.address, latitude: c.lat, longitude: c.lng });
      void lookUpAddress(c.lng, c.lat);
    });
    map.on("error", () => setNotice("The map could not load. Check your internet connection; you can still type the address."));
    return () => {
      map.remove();
      mapRef.current = null;
      gpsDot.current = null;
    };
    // Created once; later position changes are applied below with flyTo
  }, []);

  // Service center markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = serviceCenters
      .filter((c) => c.latitude != null && c.longitude != null)
      .map((c) => {
        const selected = c.id === selectedCenter?.id;
        const el = markerElement(selected ? HUB_PIN_SVG : HUB_PIN_SMALL_SVG, selected ? "" : "opacity-80");
        el.title = c.name;
        return new Marker({ element: el, anchor: "bottom" }).setLngLat([c.longitude!, c.latitude!]).addTo(map);
      });
    return () => markers.forEach((m) => m.remove());
  }, [serviceCenters, selectedCenter]);

  /** Move the map to a place chosen outside the map (search result, preset, GPS). */
  function moveTo(place: { address: string; latitude: number; longitude: number }, lookUp = false) {
    onChange(place);
    skipNextLookup.current = !lookUp;
    const map = mapRef.current;
    if (map) map.flyTo({ center: [place.longitude, place.latitude], zoom: Math.max(map.getZoom(), 16), duration: 900 });
    else if (lookUp) void lookUpAddress(place.longitude, place.latitude);
  }

  async function search() {
    if (query.trim().length < 3) return setNotice("Type at least 3 characters to search.");
    setBusy("search");
    setNotice(null);
    try {
      const res = await api<{ results: Place[] }>(`/api/location/search/?q=${encodeURIComponent(query.trim())}`);
      setResults(res.results);
      if (!res.results.length) setNotice("No places found. Try a nearby landmark, or move the map.");
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : "Search failed. Move the map or pick a preset area instead.");
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
        // Blue dot where the phone is, like map apps; the pin can still be moved away from it
        const at: LngLat = [pos.coords.longitude, pos.coords.latitude];
        const map = mapRef.current;
        if (map) gpsDot.current = (gpsDot.current ?? new Marker({ element: markerElement(GPS_DOT_HTML) }).setLngLat(at).addTo(map)).setLngLat(at);
        moveTo({ address: latest.current.address, latitude: pos.coords.latitude, longitude: pos.coords.longitude }, true);
      },
      () => {
        setBusy(null);
        setNotice("Location permission was denied. Move the map or search instead.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  const centerPoint =
    selectedCenter?.latitude != null && selectedCenter?.longitude != null ? ([selectedCenter.latitude, selectedCenter.longitude] as const) : null;
  const km = centerPoint ? haversineKm(point[1], point[0], centerPoint[0], centerPoint[1]) : null;
  const [mainLine, ...rest] = address.split(",");

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
                  moveTo({ address: r.label, latitude: r.latitude, longitude: r.longitude });
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

      {/* Map with a fixed centre pin */}
      <div className="relative overflow-hidden rounded-3xl border border-zinc-200 shadow-sm dark:border-zinc-700">
        {mapFailed ? (
          <div className="flex h-80 items-center justify-center bg-zinc-100 p-6 text-center text-xs text-zinc-500 dark:bg-zinc-800">
            This browser can't show the map (WebGL is off). Search, use your location or pick a preset area instead.
          </div>
        ) : (
          <div
            ref={containerRef}
            className="h-80 w-full"
            aria-label="Map: move it to place the pin on your pickup point"
            // Busy while the map moves or the address under the pin is being looked up
            aria-busy={moving || busy === "address"}
          />
        )}
        {!mapFailed && (
          <>
            {/* "Picked up here" bubble above the pin, as delivery apps show; hidden while the map moves */}
            <div
              className={`map-pin-bubble pointer-events-none absolute left-1/2 top-1/2 z-10 ${moving ? "hidden-while-moving" : ""}`}
              style={{ translate: "-50% calc(-100% - 56px)" }}
            >
              <div className="relative rounded-xl bg-zinc-900 px-3 py-1.5 text-center text-white shadow-lg">
                <p className="whitespace-nowrap text-xs font-bold">Your car will be picked up here</p>
                <p className="whitespace-nowrap text-[10px] text-zinc-300">Move the map to adjust the pin</p>
                <span className="absolute -bottom-1 left-1/2 h-2.5 w-2.5 -translate-x-1/2 rotate-45 bg-zinc-900" />
              </div>
            </div>
            <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-full">
              <div className={`map-center-pin drop-shadow-lg ${dragging ? "lifted" : ""}`} dangerouslySetInnerHTML={{ __html: PIN_SVG }} />
            </div>
            <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-1.5 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-black/30 blur-[1px]" />
            <button
              type="button"
              onClick={useMyLocation}
              disabled={busy !== null}
              className="absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5 whitespace-nowrap rounded-full border border-brand/30 bg-white px-4 py-2 text-xs font-bold text-brand-fg shadow-lg hover:bg-blue-50 disabled:opacity-60 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            >
              {busy === "gps" ? <LoaderCircle size={14} className="animate-spin" /> : <Crosshair size={14} />} Use current location
            </button>
          </>
        )}
      </div>

      {notice && <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">{notice}</p>}

      {/* Pickup address card, like the "deliver here" card in delivery apps */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900">
        <div className="flex items-start gap-2">
          <MapPin size={18} className="mt-0.5 shrink-0 text-brand-fg" />
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-2 text-sm font-bold">
              {busy === "address" ? "Finding address…" : mainLine || "Pickup point"}
              {busy === "address" && <LoaderCircle size={13} className="animate-spin text-zinc-400" />}
            </p>
            {rest.length > 0 && busy !== "address" && <p className="truncate text-xs text-zinc-500">{rest.join(",").trim()}</p>}
          </div>
        </div>
        <label className="mt-2 block text-xs font-semibold text-zinc-500">
          <span>Full pickup address (add flat / house number)</span>
          <textarea
            rows={2}
            className="mt-1 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={address}
            onChange={(e) => onChange({ address: e.target.value, latitude: point[1], longitude: point[0] })}
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {BENGALURU_PRESETS.map((p) => (
          <button
            key={p.name}
            type="button"
            onClick={() => moveTo({ address: p.name, latitude: p.lat, longitude: p.lng })}
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
