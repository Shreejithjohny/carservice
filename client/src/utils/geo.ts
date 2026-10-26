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
