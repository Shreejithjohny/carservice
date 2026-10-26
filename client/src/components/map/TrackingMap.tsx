import { useEffect, useMemo, useRef, useState } from "react";
import { AttributionControl, LngLatBounds, Map as MapLibreMap, Marker, NavigationControl, Popup, type GeoJSONSource } from "maplibre-gl";
import { Crosshair, MapPin, Navigation2 } from "lucide-react";
import { BRAND } from "../../utils/theme";
import { bearing } from "../../utils/geo";
import { DRIVER_SVG, MAP_STYLE_URL, PIN_SVG, markerElement, type LngLat } from "./setup";

export type RoutePoint = { latitude: number; longitude: number; timestamp: string };
type LatLng = [number, number];
export type TrackingMapProps = Readonly<{
  pickup?: LatLng | null;
  hub?: LatLng | null;
  hubName: string;
  route: RoutePoint[];
  /** Where the driver is going now; draws a dashed line from the driver to it. */
  heading?: "pickup" | "hub" | null;
}>;

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function isValid(p?: LatLng | null): p is LatLng {
  return !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]);
}
const toLngLat = (p: LatLng): LngLat => [p[1], p[0]];
const line = (coords: LngLat[]): GeoJSON.FeatureCollection =>
  coords.length > 1 ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }] } : EMPTY;

type MarkerKey = "pickup" | "hub" | "driver";

/** Add, move or remove one marker so it matches `at`; its popup shows `label`. */
function placeMarker(map: MapLibreMap, markers: Partial<Record<MarkerKey, Marker>>, key: MarkerKey, at: LngLat | null, label: string, make: () => Marker, popupOffset: number) {
  const existing = markers[key];
  if (!at) {
    existing?.remove();
    delete markers[key];
    return;
  }
  // Position before addTo: adding draws the marker, which needs a position
  const marker = existing ?? make().setLngLat(at).setPopup(new Popup({ offset: popupOffset })).addTo(map);
  marker.setLngLat(at);
  marker.getPopup()?.setText(label);
  markers[key] = marker;
}

function timeAgo(iso: string, now: number) {
  const secs = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)} min ago`;
  return `${Math.round(secs / 3600)} h ago`;
}

/** Live tracking map in the style of delivery apps: drop pin, workshop, driver arrow and route line. */
export default function TrackingMap({ pickup, hub, hubName, route, heading = null }: TrackingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Partial<Record<MarkerKey, Marker>>>({});
  const [loaded, setLoaded] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  const [recenterCount, setRecenterCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  const trail = useMemo(() => route.map((p) => [p.latitude, p.longitude] as LatLng).filter(isValid).map(toLngLat), [route]);
  const driver = trail.length ? trail[trail.length - 1] : null;
  const lastUpdate = route.length ? route[route.length - 1].timestamp : null;
  const isFresh = lastUpdate ? now - new Date(lastUpdate).getTime() < 2 * 60 * 1000 : false;
  const pickupLL = isValid(pickup) ? toLngLat(pickup) : null;
  const hubLL = isValid(hub) ? toLngLat(hub) : null;
  const targets = { pickup: pickupLL, hub: hubLL };
  const target = heading ? targets[heading] : null;
  const driverLabel = lastUpdate ? `Driver · updated ${timeAgo(lastUpdate, now)}` : "Driver";

  const points = [pickupLL, hubLL, driver].filter((p): p is LngLat => p !== null);
  const hasPoints = points.length > 0;
  const fitKey = `${!!pickupLL}-${!!hubLL}-${!!driver}-${recenterCount}`;

  // Create the map once there is something to show
  useEffect(() => {
    if (!hasPoints || !containerRef.current) return;
    let map: MapLibreMap;
    try {
      map = new MapLibreMap({ container: containerRef.current, style: MAP_STYLE_URL, center: points[0], zoom: 13, attributionControl: false });
    } catch {
      setMapFailed(true); // e.g. WebGL turned off in the browser
      return;
    }
    mapRef.current = map;
    map.scrollZoom.disable(); // the page scrolls past the map; zoom with the buttons or pinch
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    map.addControl(new AttributionControl({ compact: true }), "bottom-right");
    map.on("load", () => {
      map.addSource("trail", { type: "geojson", data: EMPTY });
      map.addSource("ahead", { type: "geojson", data: EMPTY });
      // White casing under the coloured line, like navigation apps
      map.addLayer({ id: "trail-casing", type: "line", source: "trail", layout: { "line-join": "round", "line-cap": "round" }, paint: { "line-color": "#ffffff", "line-width": 9 } });
      map.addLayer({ id: "trail", type: "line", source: "trail", layout: { "line-join": "round", "line-cap": "round" }, paint: { "line-color": BRAND, "line-width": 5 } });
      map.addLayer({ id: "ahead", type: "line", source: "ahead", layout: { "line-cap": "round" }, paint: { "line-color": BRAND, "line-width": 3, "line-dasharray": [1, 2], "line-opacity": 0.8 } });
      setLoaded(true);
    });
    return () => {
      map.remove(); // also removes its markers
      mapRef.current = null;
      markers.current = {};
      setLoaded(false);
    };
    // Created once; data changes are applied in the effects below
  }, [hasPoints]);

  // Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const m = markers.current;
    placeMarker(map, m, "pickup", pickupLL, "Pickup location", () => new Marker({ element: markerElement(PIN_SVG, "drop-shadow-lg"), anchor: "bottom" }), 40);
    placeMarker(map, m, "hub", hubLL, hubName, () => new Marker({ element: markerElement("H", "map-pin map-pin-hub") }), 18);
    placeMarker(map, m, "driver", driver, driverLabel, () => new Marker({ element: markerElement(DRIVER_SVG), rotationAlignment: "map" }), 20);
    // Point the arrow the way the driver last moved
    if (m.driver && driver && trail.length > 1) m.driver.setRotation(bearing(trail[trail.length - 2], driver));
  }, [pickupLL?.[0], pickupLL?.[1], hubLL?.[0], hubLL?.[1], hubName, trail, driver, driverLabel]);

  // Route lines
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    void (map.getSource("trail") as GeoJSONSource | undefined)?.setData(line(trail));
    void (map.getSource("ahead") as GeoJSONSource | undefined)?.setData(driver && target ? line([driver, target]) : EMPTY);
  }, [loaded, trail, driver, target?.[0], target?.[1]]);

  // Fit everything in view when what is on the map changes (or on recenter), not on every GPS
  // update, so the map does not jump while the customer is panning
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !points.length) return;
    if (points.length === 1) map.easeTo({ center: points[0], zoom: 15 });
    else {
      const bounds = points.reduce((b, p) => b.extend(p), new LngLatBounds(points[0], points[0]));
      map.fitBounds(bounds, { padding: 60, maxZoom: 15, duration: 600 });
    }
  }, [fitKey]);

  if (!hasPoints) {
    return (
      <div className="flex min-h-[370px] items-center justify-center rounded-[1.35rem] bg-zinc-100 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-800/60">
        No location available for this booking yet.
      </div>
    );
  }

  return (
    <div className="relative isolate overflow-hidden rounded-[1.35rem]">
      {mapFailed ? (
        <div className="flex h-[370px] items-center justify-center bg-zinc-100 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-800/60">
          This browser can't show the map (WebGL is off). The status above still updates live.
        </div>
      ) : (
        <div ref={containerRef} className="h-[370px] w-full" aria-label="Live service route map" />
      )}

      <div className="pointer-events-none absolute right-3 top-3 z-10 flex items-center gap-2 rounded-full bg-white/85 px-3 py-1.5 text-[11px] font-bold text-zinc-800 shadow backdrop-blur">
        {lastUpdate ? (
          <>
            <span className={isFresh ? "live-dot" : "inline-block h-[7px] w-[7px] rounded-full bg-zinc-400"} />
            {isFresh ? "Live" : "Last seen"} · driver GPS {timeAgo(lastUpdate, now)}
          </>
        ) : (
          "Waiting for the driver's GPS"
        )}
      </div>

      <button
        type="button"
        onClick={() => setRecenterCount((c) => c + 1)}
        className="absolute bottom-14 left-3 z-10 grid h-9 w-9 place-items-center rounded-xl bg-white/90 text-zinc-800 shadow"
        aria-label="Recenter map"
        title="Recenter map"
      >
        <Crosshair size={17} />
      </button>

      <div className="flex flex-wrap gap-3 px-1 pt-2 text-[11px] font-semibold text-zinc-500">
        <span className="flex items-center gap-1"><MapPin size={15} className="fill-brand text-white" strokeWidth={1.5} /> Pickup</span>
        <span className="flex items-center gap-1"><span className="map-pin map-pin-hub map-pin-sm">H</span> {hubName}</span>
        <span className="flex items-center gap-1"><span className="map-pin map-pin-driver map-pin-sm"><Navigation2 size={9} className="rotate-90 fill-white" strokeWidth={0} /></span> Driver</span>
        {heading && <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed border-brand" /> Heading to {heading === "pickup" ? "you" : hubName}</span>}
      </div>
    </div>
  );
}
