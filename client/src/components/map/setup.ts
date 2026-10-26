// Shared MapLibre setup: the map engine, its background worker and the free OpenFreeMap style.
import "maplibre-gl/dist/maplibre-gl.css";
import { setWorkerUrl } from "maplibre-gl";
// Bundled with the app (Vite emits the file), so the map never depends on a CDN for its code
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";

setWorkerUrl(workerUrl);

/**
 * Vector map style. OpenFreeMap is free with no API key or sign-up and allows any use:
 * https://openfreemap.org. Set VITE_MAP_STYLE_URL in client/.env to use another style.
 */
export const MAP_STYLE_URL: string = import.meta.env.VITE_MAP_STYLE_URL || "https://tiles.openfreemap.org/styles/liberty";

export type LngLat = [number, number];

/** A DOM element for a map marker, from a small HTML snippet. */
export function markerElement(html: string, className = ""): HTMLElement {
  const el = document.createElement("div");
  el.className = className;
  el.innerHTML = html;
  return el;
}

// Teardrop location pin, like delivery apps use for the customer's address
export const PIN_SVG = `<svg width="36" height="46" viewBox="0 0 36 46" aria-hidden="true">
  <path d="M18 45s15-15.4 15-27A15 15 0 0 0 3 18c0 11.6 15 27 15 27Z" fill="var(--color-brand)" stroke="#fff" stroke-width="2.5"/>
  <circle cx="18" cy="18" r="6" fill="#fff"/>
</svg>`;

// Navigation arrow for the driver; rotated to the direction of travel
export const DRIVER_SVG = `<div class="map-driver"><svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
  <path d="M12 2 20 21 12 16.5 4 21Z" fill="#fff"/></svg></div>`;

/** Compass bearing in degrees from one point to the next (0 = north). */
export function bearing([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const y = Math.sin(toRad(lng2 - lng1)) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(toRad(lng2 - lng1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}
