import { describe, expect, it } from "vitest";
import { favourable, formatMetric } from "../src/Summary";

describe("summary formatting", () => {
  it("formats metric units", () => {
    expect(formatMetric({ unit: "usd", value: 183031.9 })).toBe("$183,032");
    expect(formatMetric({ unit: "pct", value: -0.005 })).toBe("−0.5%");
    expect(formatMetric({ unit: "pts", value: 1 })).toBe("+1.0 pts");
    expect(formatMetric({ unit: "count", value: null })).toBe("Unavailable");
  });
  it("flips lower-is-better metrics", () => {
    expect(favourable({ direction: "up", percentile: 80 })).toBe(80);
    expect(favourable({ direction: "down", percentile: 80 })).toBe(20);
    expect(favourable({ direction: "up", percentile: null })).toBeNull();
  });
});
