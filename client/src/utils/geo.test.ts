import { describe, expect, it } from "vitest";
import { BENGALURU_PRESETS, bearing, drivingMinutes, haversineKm, lerpPoint, metersBetween, pathKm, pointsAlong, remainingRoute } from "./geo";

describe("haversineKm", () => {
  it("is zero for the same point", () => {
    expect(haversineKm(12.9716, 77.5946, 12.9716, 77.5946)).toBe(0);
  });

  it("gives 111.2 km for one degree of latitude (Earth radius 6371 km)", () => {
    expect(haversineKm(12, 77.6, 13, 77.6)).toBe(111.2);
  });

  it("shrinks east-west distances away from the equator", () => {
    // One degree of longitude is 111.2 km x cos(latitude): about 108.3 km at Bengaluru's 13 degrees N
    expect(haversineKm(13, 77, 13, 78)).toBeCloseTo(108.3, 0);
  });

  it("is the same in both directions and rounded to 0.1 km", () => {
    const there = haversineKm(12.9352, 77.6245, 13.1007, 77.5963);
    expect(haversineKm(13.1007, 77.5963, 12.9352, 77.6245)).toBe(there);
    expect(Math.round(there * 10) / 10).toBe(there);
  });
});

describe("drivingMinutes", () => {
  it("assumes about 25 km/h in the city", () => {
    expect(drivingMinutes(25)).toBe(60);
    expect(drivingMinutes(10)).toBe(24);
  });

  it("never estimates under 5 minutes", () => {
    expect(drivingMinutes(0)).toBe(5);
    expect(drivingMinutes(0.5)).toBe(5);
  });
});

describe("bearing", () => {
  const origin: [number, number] = [77.6, 12.97];

  it.each([
    ["north", [77.6, 13.0], 0],
    ["east", [77.7, 12.97], 90],
    ["south", [77.6, 12.9], 180],
    ["west", [77.5, 12.97], 270],
  ] as const)("points %s", (_, to, expected) => {
    // Small tolerance: east/west along a line of latitude is not exactly 90/270 on a sphere
    expect(bearing(origin, [to[0], to[1]])).toBeCloseTo(expected, 0);
  });

  it("always returns 0 to 360", () => {
    const b = bearing([77.6, 12.97], [77.59, 12.96]);
    expect(b).toBeGreaterThanOrEqual(0);
    expect(b).toBeLessThan(360);
  });
});

describe("BENGALURU_PRESETS", () => {
  it("all lie in the Bengaluru area", () => {
    for (const p of BENGALURU_PRESETS) {
      expect(p.lat).toBeGreaterThan(12.7);
      expect(p.lat).toBeLessThan(13.3);
      expect(p.lng).toBeGreaterThan(77.3);
      expect(p.lng).toBeLessThan(77.9);
    }
  });
});

describe("road route helpers", () => {
  // A route going east along one street, then north: about 111 m per 0.001 degree of latitude
  const route: [number, number][] = [
    [77.6, 12.97],
    [77.601, 12.97],
    [77.602, 12.97],
    [77.602, 12.971],
    [77.602, 12.972],
  ];

  it("measures metres consistently with haversineKm", () => {
    expect(metersBetween([77.6, 12], [77.6, 13]) / 1000).toBeCloseTo(haversineKm(12, 77.6, 13, 77.6), 1);
  });

  it("adds up a path's length", () => {
    // 2 x 0.001 deg of longitude at 12.97 N (about 108.4 m each) + 2 x 0.001 deg of latitude (111.2 m each)
    expect(pathKm(route)).toBeCloseTo(0.439, 2);
    expect(pathKm([[77.6, 12.97]])).toBe(0);
  });

  it("keeps only the part ahead of the driver, starting at the driver", () => {
    const driver: [number, number] = [77.6021, 12.9702]; // just past the corner
    const { path, offRouteMeters } = remainingRoute(route, driver);
    expect(path[0]).toEqual(driver);
    expect(path.slice(1)).toEqual([route[3], route[4]]);
    expect(offRouteMeters).toBeLessThan(30);
  });

  it("reports how far off the route the driver is", () => {
    expect(remainingRoute(route, [77.61, 12.98]).offRouteMeters).toBeGreaterThan(1000);
    expect(remainingRoute([], [77.6, 12.97]).offRouteMeters).toBe(Infinity);
  });

  it("measures distance to the road, not to its nearest point", () => {
    // Halfway along a 2 km straight road with points only at its ends, 10 m to the side
    const road: [number, number][] = [[77.6, 12.97], [77.6185, 12.97]];
    const { path, offRouteMeters } = remainingRoute(road, [77.60925, 12.97009]);
    expect(offRouteMeters).toBeGreaterThan(8);
    expect(offRouteMeters).toBeLessThan(12);
    expect(path).toEqual([[77.60925, 12.97009], road[1]]);
  });

  it("interpolates between two points", () => {
    expect(lerpPoint([77.6, 12.9], [77.8, 13.1], 0)).toEqual([77.6, 12.9]);
    expect(lerpPoint([77.6, 12.9], [77.8, 13.1], 1)).toEqual([77.8, 13.1]);
    const mid = lerpPoint([77.6, 12.9], [77.8, 13.1], 0.5);
    expect(mid[0]).toBeCloseTo(77.7);
    expect(mid[1]).toBeCloseTo(13.0);
  });
});

describe("pointsAlong", () => {
  // About 1.11 km due north, as two segments of different length
  const path: [number, number][] = [[77.6, 12.97], [77.6, 12.973], [77.6, 12.98]];

  it("starts at the start, ends at the end, and keeps an even spacing", () => {
    const pts = pointsAlong(path, 100);
    expect(pts[0]).toEqual(path[0]);
    expect(pts[pts.length - 1]).toEqual(path[2]);
    // 1112 m at 100 m steps: 11 steps of 100 m plus the end point
    expect(pts).toHaveLength(13);
    for (let i = 1; i < pts.length - 1; i++) expect(metersBetween(pts[i - 1], pts[i])).toBeCloseTo(100, 0);
    expect(metersBetween(pts[pts.length - 2], pts[pts.length - 1])).toBeLessThan(100);
  });

  it("keeps the spacing across a corner between segments", () => {
    // 55.6 m north, then 162.6 m east
    const corner: [number, number][] = [[77.6, 12.97], [77.6, 12.9705], [77.6015, 12.9705]];
    const pts = pointsAlong(corner, 50);
    // The second step (100 m along) is past the corner: 100 - 55.6 = 44.4 m along the east segment
    expect(pts[2][1]).toBeCloseTo(12.9705, 6);
    expect(metersBetween(corner[1], pts[2])).toBeCloseTo(44.4, 0);
    expect(pts).toHaveLength(6); // 0, 50, 100, 150, 200 m and the end at 218 m
  });

  it("handles short and empty paths", () => {
    expect(pointsAlong([], 100)).toEqual([]);
    expect(pointsAlong([[77.6, 12.97]], 100)).toEqual([[77.6, 12.97]]);
    expect(pointsAlong([[77.6, 12.97], [77.6, 12.9701]], 100)).toEqual([[77.6, 12.97], [77.6, 12.9701]]);
  });
});
