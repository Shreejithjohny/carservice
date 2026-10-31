/** Straight-line distance in km between two points (Haversine), rounded to 0.1 km. */
export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)) * 10) / 10;
}

/** Rough city driving time: about 25 km/h on average, never under 5 minutes. */
export function drivingMinutes(km: number): number {
  return Math.max(5, Math.ceil((km / 25) * 60));
}

// Common Bengaluru pickup areas, offered as one-tap presets
export const BENGALURU_PRESETS = [
  { name: "Indiranagar, Bengaluru", lat: 12.9784, lng: 77.6408 },
  { name: "Koramangala 4th Block", lat: 12.9352, lng: 77.6245 },
  { name: "Yelahanka New Town", lat: 13.1007, lng: 77.5963 },
  { name: "Whitefield Main Road", lat: 12.9698, lng: 77.7499 },
  { name: "MG Road Metro Station", lat: 12.9756, lng: 77.6066 },
];

/** Compass bearing in degrees from one [lng, lat] point to the next (0 = north, 90 = east). */
export function bearing([lng1, lat1]: [number, number], [lng2, lat2]: [number, number]): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const y = Math.sin(toRad(lng2 - lng1)) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(toRad(lng2 - lng1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

type LngLatPair = [number, number];

/** Distance in metres between two [lng, lat] points (not rounded). */
export function metersBetween([lng1, lat1]: LngLatPair, [lng2, lat2]: LngLatPair): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const a = Math.sin(toRad(lat2 - lat1) / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(toRad(lng2 - lng1) / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Length of a path of [lng, lat] points, in km. */
export function pathKm(path: LngLatPair[]): number {
  let m = 0;
  for (let i = 1; i < path.length; i++) m += metersBetween(path[i - 1], path[i]);
  return m / 1000;
}

/**
 * The part of a road route still ahead of the driver, as delivery apps draw it: from the driver's
 * position along the route to its end. `offRouteMeters` is how far the driver is from the route,
 * so the caller can fetch a new route when the driver has turned off it.
 */
export function remainingRoute(route: LngLatPair[], position: LngLatPair): { path: LngLatPair[]; offRouteMeters: number } {
  if (!route.length) return { path: [], offRouteMeters: Infinity };
  if (route.length === 1) return { path: [position], offRouteMeters: metersBetween(route[0], position) };
  // Nearest segment, measured on a flat projection (accurate at city scale): long straight roads
  // have points far apart, so the distance to the nearest point alone would be misleading
  const kx = Math.cos((position[1] * Math.PI) / 180);
  let nearest = 0;
  let best = Infinity;
  for (let i = 0; i < route.length - 1; i++) {
    const [ax, ay] = [route[i][0] * kx, route[i][1]];
    const [bx, by] = [route[i + 1][0] * kx, route[i + 1][1]];
    const [px, py] = [position[0] * kx, position[1]];
    const len2 = (bx - ax) ** 2 + (by - ay) ** 2;
    const t = len2 ? Math.max(0, Math.min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / len2)) : 0;
    const d = metersBetween(lerpPoint(route[i], route[i + 1], t), position);
    if (d < best) {
      best = d;
      nearest = i;
    }
  }
  return { path: [position, ...route.slice(nearest + 1)], offRouteMeters: best };
}

/** A point part-way between two points (t from 0 to 1), for smooth marker movement. */
export function lerpPoint([lng1, lat1]: LngLatPair, [lng2, lat2]: LngLatPair, t: number): LngLatPair {
  return [lng1 + (lng2 - lng1) * t, lat1 + (lat2 - lat1) * t];
}
