import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import { drivingMinutes, haversineKm, pathKm, remainingRoute } from "../utils/geo";

type LngLat = [number, number];
export type DrivingRoute = { coordinates: LngLat[]; distance_km: number; duration_min: number };

// Fetch a new route only when the driver has left the current one (or the destination changed),
// not on every GPS update: the free routing server asks for light use.
const OFF_ROUTE_METERS = 120;

/**
 * The road route from `from` to `to` ([lng, lat]), via our backend (OSRM). `null` while there is
 * none: no points, still loading, or routing is unavailable (then the map draws a straight line).
 */
export function useDrivingRoute(from: LngLat | null, to: LngLat | null): DrivingRoute | null {
  const [route, setRoute] = useState<DrivingRoute | null>(null);
  const requested = useRef<{ to: string; from: LngLat; id: number } | null>(null);
  const requestCount = useRef(0); // never reset, so an old answer can't pass for a newer request
  const toKey = to ? `${to[1].toFixed(5)},${to[0].toFixed(5)}` : "";

  useEffect(() => {
    if (!from || !to) {
      requested.current = null;
      setRoute(null);
      return;
    }
    const sameTarget = requested.current?.to === toKey;
    const stillOnRoute = route && sameTarget && remainingRoute(route.coordinates, from).offRouteMeters < OFF_ROUTE_METERS;
    // A request for this target from about here is already done or under way
    const nearLastRequest = sameTarget && requested.current && remainingRoute([requested.current.from], from).offRouteMeters < OFF_ROUTE_METERS;
    if (stillOnRoute || nearLastRequest) return;

    const id = ++requestCount.current;
    requested.current = { to: toKey, from, id };
    if (!sameTarget) setRoute(null); // don't keep drawing the route to the previous destination
    // Only the newest request may set the route. (Not cancelled on re-render: the driver moving a
    // few metres while it loads must not throw the answer away.)
    const isLatest = () => requested.current?.id === id;
    api<DrivingRoute>(`/api/location/route/?from=${from[1].toFixed(5)},${from[0].toFixed(5)}&to=${toKey}`)
      .then((r) => {
        if (isLatest()) setRoute(r);
      })
      .catch(() => {
        if (isLatest()) setRoute(null); // routing unavailable: the map falls back to a straight line
      });
    // Re-checked on each driver position; `route` is read, not a trigger
  }, [from?.[0], from?.[1], toKey]);

  return route;
}

export type Trip = { minutes: number; km: number; byRoad: boolean };

/**
 * Time and distance from `from` to `to`: the road route's duration scaled to the part still
 * ahead of `from`, or, without a road route, a straight-line estimate at city speed.
 * `ahead` may be passed when already worked out.
 */
export function estimateTrip(from: LngLat, to: LngLat, road: DrivingRoute | null, ahead?: LngLat[] | null): Trip {
  if (road) {
    const km = pathKm(ahead ?? remainingRoute(road.coordinates, from).path);
    const minutes = Math.max(1, Math.round(road.duration_min * Math.min(1, km / Math.max(road.distance_km, 0.1))));
    return { minutes, km: Math.round(km * 10) / 10, byRoad: true };
  }
  const km = haversineKm(from[1], from[0], to[1], to[0]);
  return { minutes: drivingMinutes(km), km, byRoad: false };
}
