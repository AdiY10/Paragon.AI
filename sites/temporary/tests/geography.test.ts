import { describe, it, expect } from "vitest";
import {
  circleCoordinates,
  EARTH_RADIUS_METERS,
  METERS_PER_MILE,
} from "../src/geography";

describe("display distance rings", () => {
  it.each([
    [41.1201, -73.375, 1],
    [26.543, -81.899, 5],
    [64.8, -147.7, 10],
  ])(
    "keeps every vertex at the intended geodesic radius (%s,%s)",
    (lat, lon, miles) => {
      const ring = circleCoordinates(lon, lat, miles);
      expect(ring).toHaveLength(129);
      expect(ring[128]).toEqual(ring[0]);
      const radians = (n: number) => (n * Math.PI) / 180;
      for (const [x, y] of ring) {
        const dLat = radians(y - lat),
          dLon = radians(x - lon);
        const a =
          Math.sin(dLat / 2) ** 2 +
          Math.cos(radians(lat)) *
            Math.cos(radians(y)) *
            Math.sin(dLon / 2) ** 2;
        const meters =
          2 * EARTH_RADIUS_METERS * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        expect(meters).toBeCloseTo(miles * METERS_PER_MILE, 5);
      }
    },
  );
  it("rejects invalid coordinates and radii instead of drawing a misleading ring", () => {
    expect(() => circleCoordinates(-73, 91, 3)).toThrow();
    expect(() => circleCoordinates(-73, 41, 0)).toThrow();
    expect(() => circleCoordinates(NaN, 41, 3)).toThrow();
  });
});
