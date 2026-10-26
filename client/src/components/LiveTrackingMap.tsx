import { lazy, Suspense } from "react";
import type { TrackingMapProps } from "./map/TrackingMap";

export type { RoutePoint } from "./map/TrackingMap";

// The map engine is large, so it loads only on pages that show a map
const TrackingMap = lazy(() => import("./map/TrackingMap"));

export function LiveTrackingMap(props: TrackingMapProps) {
  return (
    <Suspense fallback={<div className="h-[370px] animate-pulse rounded-[1.35rem] bg-zinc-100 dark:bg-zinc-800/60" />}>
      <TrackingMap {...props} />
    </Suspense>
  );
}
