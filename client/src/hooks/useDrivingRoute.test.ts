import { describe, expect, it } from "vitest";
import { estimateTrip, type DrivingRoute } from "./useDrivingRoute";

describe("estimateTrip", () => {
  // A 2-segment road route of about 0.44 km (see geo.test.ts) taking 4 minutes
  const road: DrivingRoute = {
    coordinates: [[77.6, 12.97], [77.602, 12.97], [77.602, 12.972]],
    distance_km: 0.44,
    duration_min: 4,
  };

  it("uses the whole road route from its start", () => {
    expect(estimateTrip([77.6, 12.97], [77.602, 12.972], road)).toEqual({ minutes: 4, km: 0.4, byRoad: true });
  });

  it("scales the time to the part of the route still ahead", () => {
    // At the corner: only the northbound 222 m remains, about half the route
    const trip = estimateTrip([77.602, 12.97], [77.602, 12.972], road);
    expect(trip.byRoad).toBe(true);
    expect(trip.km).toBeCloseTo(0.2, 1);
    expect(trip.minutes).toBe(2);
  });

  it("falls back to a straight-line estimate at city speed without a road route", () => {
    // 111.2 km north at 25 km/h
    expect(estimateTrip([77.6, 12], [77.6, 13], null)).toEqual({ minutes: 267, km: 111.2, byRoad: false });
  });
});
