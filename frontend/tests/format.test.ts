import { describe, expect, it } from "vitest";
import {
  checkedLabel,
  count,
  dateLabel,
  distanceMi,
  favourable,
  floodHeadline,
  floodShort,
  floodTone,
  formatChange,
  formatChangePct,
  formatCompact,
  formatInt,
  formatMetric,
  formatMoe,
  formatShare,
  formatIncome,
  formatUsd,
  formatValue,
  indexText,
  monthLabel,
  ordinal,
  perDay,
  rankSentence,
  rankText,
  reasonText,
  reliabilityLabel,
  signedPct,
  signedPts,
  significanceText,
  trendTone,
  type Metric,
  type Trend,
} from "../src/lib/format";
// Old import paths keep working until WI-9.
import { count as legacyCount } from "../src/area";
import { formatValue as legacyFormatValue } from "../src/demographics";
import { formatMetric as legacyFormatMetric } from "../src/Summary";
import { dateLabel as legacyDateLabel } from "../src/api";

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

describe("numbers", () => {
  it("formats integers, money, shares and compact values", () => {
    expect(formatInt(84000)).toBe("84,000");
    expect(formatUsd(183031.9)).toBe("$183,032");
    expect(formatShare(0.5004)).toBe("50.0%");
    expect(formatCompact(1284)).toBe("1,284");
    expect(formatCompact(12940)).toBe("12.9K");
    expect(formatCompact(4_200_000)).toBe("4.2M");
    expect(formatCompact(-25_000)).toBe("−25K");
    expect(formatIncome(133405)).toBe("$133,405");
    expect(formatIncome(200000)).toBe("≥ $200,000");
    expect(formatIncome(null)).toBeNull();
  });
  it("formats signed changes with a true minus sign", () => {
    expect(formatChangePct(0.031)).toBe("+3.1%");
    expect(formatChangePct(-0.098)).toBe("−9.8%");
    expect(formatChangePct(0.0001)).toBe("0.0%");
  });
  it("returns null for missing values, never zero", () => {
    for (const fn of [formatInt, formatUsd, formatShare, formatCompact, formatChangePct, perDay, distanceMi, indexText])
      expect(fn(null)).toBeNull();
    expect(formatInt(Number.NaN)).toBeNull();
    expect(rankText(null, 35)).toBeNull();
    expect(floodShort(null)).toBeNull();
  });
  it("words ranks for properties and new places", () => {
    expect(rankText(3, 35)).toBe("3 of 35");
    expect(rankSentence(3, 35)).toBe("Ranks 3 of 35 owned properties");
    expect(rankSentence(3, 35, "place")).toBe("Would rank 3 of 35 owned properties");
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 101].map(ordinal)).toEqual([
      "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st",
    ]);
  });
  it("describes traffic as vehicles, distances in miles and indexes vs the US", () => {
    expect(perDay(21000)).toBe("21,000 vehicles/day");
    expect(distanceMi(0.46)).toBe("0.5 mi");
    expect(distanceMi(0.01)).toBe("<0.1 mi");
    expect(distanceMi(12.3)).toBe("12 mi");
    expect(indexText(112.4)).toBe("112 · 12% above the US average");
    expect(indexText(88)).toBe("88 · 12% below the US average");
    expect(indexText(100.2)).toBe("100 · same as the US average");
  });
  it("labels list-level flood status", () => {
    expect(floodShort("inside")).toBe("Inside high-risk zone");
    expect(floodShort("near")).toBe("Near high-risk zone");
    expect(floodShort("none")).toBe("Not in a high-risk zone");
  });
});

describe("dates", () => {
  it("labels dates in Eastern time and never says 'checked Not checked'", () => {
    expect(dateLabel("2026-11-21")).toBe("Nov 21, 2026");
    expect(checkedLabel(null)).toBe("not checked yet");
    expect(checkedLabel("2026-11-21")).toBe("checked Nov 21, 2026");
  });
});

describe("area formatting", () => {
  it("formats real Ulster County and Kingston values", () => {
    expect(count(47301)).toBe("47,301");
    expect(signedPct(0.048)).toBe("+4.8%");
    expect(signedPct(-0.004484)).toBe("−0.4%"); // Kingston US 9W 2024→2025
    expect(signedPts(0.2)).toBe("+0.2 pts");
    expect(monthLabel("12 months to 2026-09")).toBe("12 months to Sep 2026");
  });
  it("never shows missing values as zero", () => {
    expect(count(null)).toBe("Unavailable");
    expect(signedPct(null, "GEOGRAPHY_CHANGED")).toContain("geography");
    expect(signedPts(null)).toBe("No comparison");
  });
  it("describes FEMA zones without overstating", () => {
    expect(floodHeadline({ zone: "AE", sfha: true, reason: null })).toContain("Special Flood Hazard Area");
    expect(floodTone({ zone: "AE", sfha: true, reason: null })).toBe("red");
    expect(floodHeadline({ zone: "X", sfha: false, risk: "minimal", reason: null })).toContain("minimal");
    expect(floodHeadline({ zone: null, reason: "NOT_COVERED" })).toBe("Not covered");
  });
});

describe("ring demographic formatting", () => {
  it("formats real Norwalk values by unit", () => {
    expect(formatValue(metric({ value: 85543.6, moe: 3802 }))).toBe("85,544");
    expect(formatMoe(metric({ value: 85543.6, moe: 3802 }))).toBe("± 3,802");
    expect(formatValue(metric({ unit: "usd", value: 183031.9 }))).toBe("$183,032");
    expect(formatValue(metric({ unit: "share", value: 0.5004 }))).toBe("50.0%");
    expect(formatMoe(metric({ unit: "share", value: 0.5, moe: 0.021 }))).toBe("± 2.1 pts");
  });
  it("shows the open-ended median floor instead of a guessed number", () => {
    expect(formatValue(metric({ unit: "usd", value: 200000, open_ended: true, display: "≥ $200,000" }))).toBe(
      "≥ $200,000",
    );
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

describe("summary metric formatting", () => {
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

describe("re-export stubs", () => {
  it("keep the old import paths working", () => {
    expect(legacyCount(5)).toBe("5");
    expect(legacyFormatValue(metric({ value: 10 }))).toBe("10");
    expect(legacyFormatMetric({ unit: "count", value: 3 })).toBe("3");
    expect(legacyDateLabel("2026-01-02")).toBe("Jan 2, 2026");
  });
});
