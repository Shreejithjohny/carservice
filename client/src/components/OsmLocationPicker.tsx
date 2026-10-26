import { lazy, Suspense, type ComponentProps } from "react";

// The map engine is large, so it loads only on pages that show a map
const MapLocationPicker = lazy(() => import("./map/MapLocationPicker"));

/** Free pickup-point picker (OpenFreeMap vector map, no API key), used when Google Maps is not set up. */
export function OsmLocationPicker(props: ComponentProps<typeof MapLocationPicker>) {
  return (
    <Suspense fallback={<div className="h-72 animate-pulse rounded-3xl bg-zinc-100 dark:bg-zinc-800/60" />}>
      <MapLocationPicker {...props} />
    </Suspense>
  );
}
