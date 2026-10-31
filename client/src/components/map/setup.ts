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

// Teardrop pin with an icon inside (24x24 Lucide-style paths, drawn in white)
function iconPin(color: string, iconPaths: string, size = 36): string {
  const h = Math.round(size * 46 / 36);
  return `<svg width="${size}" height="${h}" viewBox="0 0 36 46" aria-hidden="true">
  <path d="M18 45s15-15.4 15-27A15 15 0 0 0 3 18c0 11.6 15 27 15 27Z" fill="${color}" stroke="#fff" stroke-width="2.5"/>
  <svg x="9" y="9" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${iconPaths}</svg>
</svg>`;
}

const HOUSE = '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>';
const WRENCH =
  '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>';

// Plain teardrop for the fixed centre pin on the Book page
export const PIN_SVG = `<svg width="36" height="46" viewBox="0 0 36 46" aria-hidden="true">
  <path d="M18 45s15-15.4 15-27A15 15 0 0 0 3 18c0 11.6 15 27 15 27Z" fill="var(--color-brand)" stroke="#fff" stroke-width="2.5"/>
  <circle cx="18" cy="18" r="6" fill="#fff"/>
</svg>`;

/** The customer's pickup point: a home pin, as delivery apps mark "your address". */
export const HOME_PIN_SVG = iconPin("var(--color-brand)", HOUSE);
/** A workshop (service center): a dark pin with a wrench. */
export const HUB_PIN_SVG = iconPin("#151923", WRENCH);
export const HUB_PIN_SMALL_SVG = iconPin("#151923", WRENCH, 26);

/** The driver: a car seen from above, pointing up (north); the marker is rotated to the direction of travel. */
export const CAR_SVG = `<div class="map-car"><svg width="24" height="42" viewBox="0 0 24 42" aria-hidden="true">
  <rect x="2" y="2" width="20" height="38" rx="8" fill="var(--color-brand)" stroke="#fff" stroke-width="2"/>
  <path d="M5.5 12.5c1.8-1.6 11.2-1.6 13 0l-1 5.5h-11z" fill="#dbeafe"/>
  <path d="M6.5 30h11l.8 4c-1.6 1.3-11 1.3-12.6 0z" fill="#dbeafe" opacity=".85"/>
  <rect x="8" y="20" width="8" height="8" rx="1.5" fill="#1d4ed8" opacity=".35"/>
</svg></div>`;

/** The phone's own position: a blue dot with a pulsing halo. */
export const GPS_DOT_HTML = '<span class="map-gps-dot"></span>';
