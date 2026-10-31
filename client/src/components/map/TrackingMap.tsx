import { useEffect, useMemo, useRef, useState } from "react";
import { AttributionControl, LngLatBounds, Map as MapLibreMap, Marker, NavigationControl, Popup, type GeoJSONSource } from "maplibre-gl";
import { Car, Crosshair, House, Wrench } from "lucide-react";
import { BRAND } from "../../utils/theme";
import { bearing, drivingMinutes, haversineKm, lerpPoint, metersBetween, pathKm, remainingRoute } from "../../utils/geo";
import { useDrivingRoute, type DrivingRoute } from "../../hooks/useDrivingRoute";
import { CAR_SVG, HOME_PIN_SVG, HUB_PIN_SVG, MAP_STYLE_URL, markerElement, type LngLat } from "./setup";

export type RoutePoint = { latitude: number; longitude: number; timestamp: string };
type LatLng = [number, number];
export type TrackingMapProps = Readonly<{
  pickup?: LatLng | null;
  hub?: LatLng | null;
  hubName: string;
  route: RoutePoint[];
  /** Where the driver is going now: the map draws the road route there and shows the ETA. */
  heading?: "pickup" | "hub" | null;
}>;

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const GLIDE_MS = 1200; // how long the car takes to glide to a new GPS position

function isValid(p?: LatLng | null): p is LatLng {
  return !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]);
}
const toLngLat = (p: LatLng): LngLat => [p[1], p[0]];
const line = (coords: LngLat[]): GeoJSON.FeatureCollection =>
  coords.length > 1 ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }] } : EMPTY;
const prefersReducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

type MarkerKey = "pickup" | "hub";

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

type Eta = { minutes: number; km: number; byRoad: boolean };

/**
 * Time and distance left: the road route's duration scaled to the part still ahead, or, without a
 * road route, a straight-line estimate at city speed.
 */
function estimateArrival(driver: LngLat | null, target: LngLat | null, road: DrivingRoute | null, ahead: LngLat[] | null): Eta | null {
  if (!driver || !target) return null;
  if (road && ahead) {
    const km = pathKm(ahead);
    const minutes = Math.max(1, Math.round(road.duration_min * Math.min(1, km / Math.max(road.distance_km, 0.1))));
    return { minutes, km: Math.round(km * 10) / 10, byRoad: true };
  }
  const km = haversineKm(driver[1], driver[0], target[1], target[0]);
  return { minutes: drivingMinutes(km), km, byRoad: false };
}

type Car = { marker: Marker; shown: LngLat; frame: number };

/** Glide the car from where it is shown to `to` (ease in-out); jump for big gaps or reduced motion. */
function glideCar(car: Car, to: LngLat) {
  cancelAnimationFrame(car.frame);
  const from = car.shown;
  if (prefersReducedMotion() || metersBetween(from, to) > 2000) {
    car.shown = to;
    car.marker.setLngLat(to);
    return;
  }
  const start = performance.now();
  const step = (time: number) => {
    const t = Math.min(1, (time - start) / GLIDE_MS);
    const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
    car.shown = lerpPoint(from, to, eased);
    car.marker.setLngLat(car.shown);
    if (t < 1) car.frame = requestAnimationFrame(step);
  };
  car.frame = requestAnimationFrame(step);
}

function GpsBadge({ lastUpdate, now }: Readonly<{ lastUpdate: string | null; now: number }>) {
  const isFresh = lastUpdate ? now - new Date(lastUpdate).getTime() < 2 * 60 * 1000 : false;
  return (
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
  );
}

/** "Driver arriving in 7 min", as the delivery apps show over the map. */
function EtaCard({ eta, title }: Readonly<{ eta: Eta; title: string }>) {
  return (
    <section
      aria-label="Estimated arrival"
      className="absolute bottom-3 left-3 z-10 flex items-center gap-3 rounded-2xl bg-white/95 py-2 pl-2.5 pr-4 text-zinc-900 shadow-lg backdrop-blur dark:bg-zinc-900/95 dark:text-white"
    >
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand text-white">
        <Car size={20} />
      </span>
      <span>
        <span className="block text-[11px] font-semibold text-zinc-500">{title}</span>
        <span className="block text-xl font-black leading-tight">
          {eta.minutes} min{eta.byRoad ? "" : "*"}
        </span>
        <span className="block text-[11px] text-zinc-500">
          {eta.km} km {eta.byRoad ? "by road" : "away · *straight-line estimate"}
        </span>
      </span>
    </section>
  );
}

function fitTo(map: MapLibreMap, points: LngLat[]) {
  if (!points.length) return;
  if (points.length === 1) {
    map.easeTo({ center: points[0], zoom: 15, duration: 800 });
    return;
  }
  const bounds = points.reduce((b, p) => b.extend(p), new LngLatBounds(points[0], points[0]));
  // Room for the pins (drawn above their point) under the GPS badge, and for the ETA card at the bottom
  map.fitBounds(bounds, { padding: { top: 100, right: 60, bottom: 110, left: 60 }, maxZoom: 16, duration: 800 });
}

/**
 * Live tracking map in the style of delivery apps: the customer's home pin, the workshop, the
 * driver's car gliding along the road route, the route still ahead, and an ETA card. The camera
 * follows the driver until the customer moves the map; Recenter turns following back on.
 */
export default function TrackingMap({ pickup, hub, hubName, route, heading = null }: TrackingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markers = useRef<Partial<Record<MarkerKey, Marker>>>({});
  const car = useRef<Car | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [mapFailed, setMapFailed] = useState(false);
  const [follow, setFollow] = useState(true);
  const [recenterCount, setRecenterCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  const trail = useMemo(() => route.map((p) => [p.latitude, p.longitude] as LatLng).filter(isValid).map(toLngLat), [route]);
  const driver = trail.length ? trail[trail.length - 1] : null;
  const lastUpdate = route.length ? route[route.length - 1].timestamp : null;
  const pickupLL = isValid(pickup) ? toLngLat(pickup) : null;
  const hubLL = isValid(hub) ? toLngLat(hub) : null;
  const targets = { pickup: pickupLL, hub: hubLL };
  const target = heading ? targets[heading] : null;
  const destinationName = heading === "hub" ? hubName : "you";

  // Road route to where the driver is going; until it loads (or if routing is down) a straight line
  const road = useDrivingRoute(driver, target);
  const ahead = useMemo(() => (road && driver ? remainingRoute(road.coordinates, driver).path : null), [road, driver]);
  const eta = estimateArrival(driver, target, road, ahead);

  const points = [pickupLL, hubLL, driver].filter((p): p is LngLat => p !== null);
  const hasPoints = points.length > 0;

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
    // The customer moved the map themselves: stop following the driver until Recenter
    const stopFollowing = (e: { originalEvent?: unknown }) => {
      if (e.originalEvent) setFollow(false);
    };
    map.on("dragstart", stopFollowing);
    map.on("zoomstart", stopFollowing);
    map.on("load", () => {
      for (const id of ["trail", "ahead-road", "ahead-straight"]) map.addSource(id, { type: "geojson", data: EMPTY });
      const round = { "line-join": "round", "line-cap": "round" } as const;
      // Where the driver has been: a thin grey line, as apps show the finished part
      map.addLayer({ id: "trail", type: "line", source: "trail", layout: round, paint: { "line-color": "#94a3b8", "line-width": 3, "line-opacity": 0.8 } });
      // The road route still ahead: brand colour on a white casing
      map.addLayer({ id: "ahead-road-casing", type: "line", source: "ahead-road", layout: round, paint: { "line-color": "#ffffff", "line-width": 10 } });
      map.addLayer({ id: "ahead-road", type: "line", source: "ahead-road", layout: round, paint: { "line-color": BRAND, "line-width": 6 } });
      // No road route available: a dashed straight line instead
      map.addLayer({ id: "ahead-straight", type: "line", source: "ahead-straight", layout: { "line-cap": "round" }, paint: { "line-color": BRAND, "line-width": 3, "line-dasharray": [1, 2], "line-opacity": 0.8 } });
      setLoaded(true);
    });
    return () => {
      if (car.current) cancelAnimationFrame(car.current.frame);
      map.remove(); // also removes its markers
      mapRef.current = null;
      markers.current = {};
      car.current = null;
      setLoaded(false);
    };
    // Created once; data changes are applied in the effects below
  }, [hasPoints]);

  // Home and workshop pins
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const m = markers.current;
    placeMarker(map, m, "pickup", pickupLL, "Pickup location", () => new Marker({ element: markerElement(HOME_PIN_SVG), anchor: "bottom" }), 44);
    placeMarker(map, m, "hub", hubLL, hubName, () => new Marker({ element: markerElement(HUB_PIN_SVG), anchor: "bottom" }), 44);
  }, [pickupLL?.[0], pickupLL?.[1], hubLL?.[0], hubLL?.[1], hubName]);

  // The driver's car: glides from where it is shown to each new GPS position, turned the way it drives
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!driver) {
      car.current?.marker.remove();
      car.current = null;
      return;
    }
    if (!car.current) {
      const marker = new Marker({ element: markerElement(CAR_SVG), rotationAlignment: "map" }).setLngLat(driver).setPopup(new Popup({ offset: 24 })).addTo(map);
      car.current = { marker, shown: driver, frame: 0 };
    }
    const c = car.current;
    const previous = trail.length > 1 ? trail[trail.length - 2] : c.shown;
    if (metersBetween(previous, driver) > 3) c.marker.setRotation(bearing(previous, driver));
    glideCar(c, driver);
  }, [driver?.[0], driver?.[1], hasPoints]);

  useEffect(() => {
    car.current?.marker.getPopup()?.setText(lastUpdate ? `Driver · updated ${timeAgo(lastUpdate, now)}` : "Driver");
  }, [lastUpdate, now, driver?.[0], driver?.[1]]);

  // Route lines
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const source = (id: string) => map.getSource(id) as GeoJSONSource | undefined;
    void source("trail")?.setData(line(trail));
    void source("ahead-road")?.setData(ahead ? line(ahead) : EMPTY);
    void source("ahead-straight")?.setData(!ahead && driver && target ? line([driver, target]) : EMPTY);
  }, [loaded, trail, ahead, driver, target?.[0], target?.[1]]);

  // Camera: keep the driver and where they are going in view on every update, while following
  const viewKey = [pickupLL, hubLL, driver, target].map((p) => (p ? `${p[0].toFixed(5)},${p[1].toFixed(5)}` : "-")).join("|");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !follow) return;
    fitTo(map, driver && target ? [driver, target] : points);
  }, [viewKey, follow, recenterCount]);

  if (!hasPoints) {
    return (
      <div className="flex min-h-[370px] items-center justify-center rounded-[1.35rem] bg-zinc-100 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-800/60">
        No location available for this booking yet.
      </div>
    );
  }

  return (
    <div>
      {/* Map and everything drawn over it; the legend sits below */}
      <div className="relative isolate overflow-hidden rounded-[1.35rem]">
        {mapFailed ? (
          <div className="flex h-[370px] items-center justify-center bg-zinc-100 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-800/60">
            This browser can't show the map (WebGL is off). The status above still updates live.
          </div>
        ) : (
          <div ref={containerRef} className="h-[370px] w-full" aria-label="Live service route map" />
        )}

        <GpsBadge lastUpdate={lastUpdate} now={now} />
        {eta && <EtaCard eta={eta} title={heading === "hub" ? `Reaching ${hubName} in` : "Driver arriving in"} />}

        <button
          type="button"
          onClick={() => {
            setFollow(true);
            setRecenterCount((c) => c + 1);
          }}
          className={`absolute bottom-10 right-3 z-10 flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-xs font-bold shadow ${
            follow ? "bg-white/90 text-zinc-800" : "bg-brand text-white"
          }`}
          aria-label="Recenter map"
          title="Recenter map"
        >
          <Crosshair size={17} />
          {!follow && <span>Re-centre</span>}
        </button>
      </div>

      <div className="flex flex-wrap gap-3 px-1 pt-2 text-[11px] font-semibold text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="grid h-[18px] w-[18px] place-items-center rounded-full bg-brand text-white"><House size={10} /></span> Pickup
        </span>
        <span className="flex items-center gap-1">
          <span className="grid h-[18px] w-[18px] place-items-center rounded-full bg-[#151923] text-white"><Wrench size={10} /></span> {hubName}
        </span>
        <span className="flex items-center gap-1">
          <span className="grid h-[18px] w-[18px] place-items-center rounded-full bg-brand text-white"><Car size={10} /></span> Driver
        </span>
        {heading && (
          <span className="flex items-center gap-1">
            <span className="h-1 w-4 rounded-full bg-brand" /> Route to {destinationName}
          </span>
        )}
      </div>
    </div>
  );
}
