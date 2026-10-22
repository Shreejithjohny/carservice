import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { Crosshair } from "lucide-react";

export type RoutePoint = { latitude: number; longitude: number; timestamp: string };
type LatLng = [number, number];

// Plain HTML markers avoid Leaflet's default image icons, which break under Vite bundling.
function pin(className: string, label: string) {
  return L.divIcon({
    className: "",
    html: `<div class="map-pin ${className}">${label}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -14],
  });
}
const ICONS = {
  pickup: pin("map-pin-pickup", "P"),
  hub: pin("map-pin-hub", "H"),
  driver: pin("map-pin-driver", "D"),
};

function isValid(p?: LatLng | null): p is LatLng {
  return !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]);
}

function FitToPoints({ points, fitKey }: { points: LatLng[]; fitKey: string }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) map.setView(points[0], 15);
    else map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    // Refit only when the set of things on the map changes (or on recenter), not on every GPS update,
    // so the map does not jump while the customer is panning.
  }, [map, fitKey]);
  return null;
}

function timeAgo(iso: string, now: number) {
  const secs = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)} min ago`;
  return `${Math.round(secs / 3600)} h ago`;
}

export function LiveTrackingMap({
  pickup,
  hub,
  hubName,
  route,
}: {
  pickup?: LatLng | null;
  hub?: LatLng | null;
  hubName: string;
  route: RoutePoint[];
}) {
  const [recenterCount, setRecenterCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  const trail = useMemo(() => route.map((p) => [p.latitude, p.longitude] as LatLng).filter(isValid), [route]);
  const driver = trail.length ? trail[trail.length - 1] : null;
  const lastUpdate = route.length ? route[route.length - 1].timestamp : null;
  const isFresh = lastUpdate ? now - new Date(lastUpdate).getTime() < 2 * 60 * 1000 : false;

  const points = [pickup, hub, driver].filter(isValid);
  const fitKey = `${isValid(pickup)}-${isValid(hub)}-${!!driver}-${recenterCount}`;

  if (!points.length) {
    return (
      <div className="flex min-h-[370px] items-center justify-center rounded-[1.35rem] bg-zinc-100 p-6 text-center text-sm text-zinc-500 dark:bg-zinc-800/60">
        No location available for this booking yet.
      </div>
    );
  }

  return (
    <div className="relative isolate overflow-hidden rounded-[1.35rem]">
      <MapContainer center={points[0]} zoom={13} scrollWheelZoom={false} className="h-[370px] w-full" aria-label="Live service route map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToPoints points={points} fitKey={fitKey} />
        {isValid(pickup) && (
          <Marker position={pickup} icon={ICONS.pickup}>
            <Popup>Pickup location</Popup>
          </Marker>
        )}
        {isValid(hub) && (
          <Marker position={hub} icon={ICONS.hub}>
            <Popup>{hubName}</Popup>
          </Marker>
        )}
        {trail.length > 1 && <Polyline positions={trail} pathOptions={{ color: "#ff4d2e", weight: 4, opacity: 0.8 }} />}
        {driver && (
          <Marker position={driver} icon={ICONS.driver}>
            <Popup>Driver{lastUpdate ? ` · updated ${timeAgo(lastUpdate, now)}` : ""}</Popup>
          </Marker>
        )}
      </MapContainer>

      <div className="pointer-events-none absolute right-3 top-3 z-[1000] flex items-center gap-2 rounded-full bg-white/85 px-3 py-1.5 text-[11px] font-bold text-zinc-800 shadow backdrop-blur">
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
        className="absolute bottom-12 left-3 z-[1000] grid h-9 w-9 place-items-center rounded-xl bg-white/90 text-zinc-800 shadow"
        aria-label="Recenter map"
        title="Recenter map"
      >
        <Crosshair size={17} />
      </button>

      <div className="flex flex-wrap gap-3 px-1 pt-2 text-[11px] font-semibold text-zinc-500">
        <span className="flex items-center gap-1"><span className="map-pin map-pin-pickup map-pin-sm">P</span> Pickup</span>
        <span className="flex items-center gap-1"><span className="map-pin map-pin-hub map-pin-sm">H</span> {hubName}</span>
        <span className="flex items-center gap-1"><span className="map-pin map-pin-driver map-pin-sm">D</span> Driver</span>
      </div>
    </div>
  );
}
