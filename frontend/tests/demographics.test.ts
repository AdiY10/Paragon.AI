import { describe, expect, it } from "vitest";
import {
  formatChange,
  formatMoe,
  formatValue,
  reasonText,
  reliabilityLabel,
  significanceText,
  trendTone,
  type Metric,
  type Trend,
} from "../src/demographics";

const metric = (m: Partial<Metric>): Metric => ({
  metric_id: "MET-01",
  value: 1,
  moe: null,
  reliability: "high",
  reason: null,
  unit: "people",
  label: "Estimate",
  ...m,
});
const trend = (t: Partial<Trend>): Trend => ({ metric_id: "MET-06", value: 0.07, ...t });

describe("ring demographic formatting", () => {
  it("formats real Norwalk values by unit", () => {
    expect(formatValue(metric({ value: 85543.6, moe: 3802 }))).toBe("85,544");
    expect(formatMoe(metric({ value: 85543.6, moe: 3802 }))).toBe("± 3,802");
    expect(formatValue(metric({ unit: "usd", value: 183031.9 }))).toBe("$183,032");
    expect(formatValue(metric({ unit: "share", value: 0.5004 }))).toBe("50.0%");
    expect(formatMoe(metric({ unit: "share", value: 0.5, moe: 0.021 }))).toBe("± 2.1 pts");
  });
  it("shows the open-ended median floor instead of a guessed number", () => {
    expect(
      formatValue(metric({ unit: "usd", value: 200000, open_ended: true, display: "≥ $200,000" })),
    ).toBe("≥ $200,000");
  });
  it("never renders a missing value as zero", () => {
    expect(formatValue(metric({ value: null, reason: "SUPPRESSED" }))).toBe("Not published by Census");
    expect(formatValue(undefined)).toBe("Unavailable");
    expect(formatMoe(metric({ value: null }))).toBeNull();
    expect(reasonText("GEOGRAPHY_CHANGED")).toContain("geography");
  });
  it("flags only low and very low reliability", () => {
    expect(reliabilityLabel("high")).toBeNull();
    expect(reliabilityLabel("medium")).toBeNull();
    expect(reliabilityLabel("very_low")).toBe("Very low reliability");
  });
  it("colours trends only when statistically significant", () => {
    expect(formatChange(trend({ value: 0.0701 }))).toBe("+7.0%");
    expect(formatChange(trend({ value: -0.013 }))).toBe("−1.3%");
    expect(trendTone(trend({ value: 0.07, significant: true }))).toBe("up");
    expect(trendTone(trend({ value: -0.2, significant: false }))).toBe("flat");
    expect(significanceText(trend({ significant: null }))).toBe("Significance not tested");
    expect(formatChange(trend({ value: null, reason: "SOURCE_ERROR" }))).toBe("Source unavailable");
  });
});
