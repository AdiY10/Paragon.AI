import { describe, expect, it } from "vitest";
import { clusterPoints } from "../src/lib/cluster";

describe("clusterPoints", () => {
  it("keeps points farther apart than the radius as singletons", () => {
    const result = clusterPoints([
      { id: "a", x: 0, y: 0 },
      { id: "b", x: 100, y: 0 },
      { id: "c", x: 0, y: 100 },
    ]);
    expect(result.map((c) => c.ids)).toEqual([["a"], ["b"], ["c"]]);
  });
  it("groups points within 40 px of the seed and centres the cluster on them", () => {
    const result = clusterPoints([
      { id: "a", x: 10, y: 10 },
      { id: "b", x: 30, y: 10 },
      { id: "c", x: 10, y: 40 },
      { id: "far", x: 300, y: 300 },
    ]);
    expect(result).toHaveLength(2);
    expect(result[0].ids).toEqual(["a", "b", "c"]);
    expect(result[0].x).toBeCloseTo(50 / 3);
    expect(result[0].y).toBeCloseTo(20);
    expect(result[1].ids).toEqual(["far"]);
  });
  it("uses the radius boundary inclusively and respects a custom radius", () => {
    expect(clusterPoints([{ id: "a", x: 0, y: 0 }, { id: "b", x: 40, y: 0 }])).toHaveLength(1);
    expect(clusterPoints([{ id: "a", x: 0, y: 0 }, { id: "b", x: 41, y: 0 }])).toHaveLength(2);
    expect(clusterPoints([{ id: "a", x: 0, y: 0 }, { id: "b", x: 60, y: 0 }], 80)).toHaveLength(1);
  });
  it("assigns every point exactly once and gives stable keys", () => {
    const points = Array.from({ length: 200 }, (_, i) => ({ id: `p${i}`, x: (i * 37) % 500, y: (i * 91) % 400 }));
    const result = clusterPoints(points);
    const ids = result.flatMap((c) => c.ids);
    expect(ids).toHaveLength(200);
    expect(new Set(ids).size).toBe(200);
    const again = clusterPoints([...points]);
    expect(again.map((c) => c.key)).toEqual(result.map((c) => c.key));
    expect(result.find((c) => c.ids.length > 1)!.key).toBe([...result.find((c) => c.ids.length > 1)!.ids].sort().join("|"));
  });
  it("handles an empty list", () => {
    expect(clusterPoints([])).toEqual([]);
  });
});
