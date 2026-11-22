import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Kpi } from "../src/api/types";
import { KpiGrid, kpiChange, kpiRank, kpiSub, kpiValue } from "../src/features/analysis/KpiCard";

const kpi = (k: Partial<Kpi>): Kpi => ({ key: "population", label: "People within 3 mi", value: 67312, unit: "people", ...k });

describe("KPI values", () => {
  it("formats by unit and never invents a missing value", () => {
    expect(kpiValue(kpi({}))).toBe("67,312");
    expect(kpiValue(kpi({ unit: "usd", value: 67968 }))).toBe("$67,968");
    expect(kpiValue(kpi({ unit: "usd", value: 200000 }))).toBe("≥ $200,000");
    expect(kpiValue(kpi({ unit: "usd", value: 200000, display: "≥ $200,000" }))).toBe("≥ $200,000");
    expect(kpiValue(kpi({ unit: "per_day", value: 21000 }))).toBe("21,000");
    expect(kpiValue(kpi({ unit: "mi", value: 0.5, display: "Publix" }))).toBe("Publix");
    expect(kpiValue(kpi({ unit: "text", value: null, display: "Inside zone AE" }))).toBe("Inside zone AE");
    expect(kpiValue(kpi({ value: null }))).toBeNull();
    expect(kpiValue(kpi({ unit: "text", value: null, display: null }))).toBeNull();
  });
  it("adds units and context under the value", () => {
    expect(kpiSub(kpi({ unit: "per_day", value: 21000, detail: "NC-87" }))).toBe("vehicles/day on NC-87");
    expect(kpiSub(kpi({ unit: "mi", value: 0.5, display: "Publix" }))).toBe("0.5 mi away");
  });
});

describe("KPI cards from the B6b bundle", () => {
  it("handles the flood level, vehicles, places, the supermarket, notes and the US index", () => {
    const flood = kpi({ key: "flood", unit: null, value: "inside", detail: "Inside FEMA high-risk flood zone AE (base flood elevation 9 ft)" });
    expect(kpiValue(flood)).toBe("Inside high-risk zone");
    expect(kpiSub(flood)).toBe("Inside FEMA high-risk flood zone AE (base flood elevation 9 ft)");
    expect(kpiValue(kpi({ key: "flood", unit: null, value: "none" }))).toBe("Not in a high-risk zone");
    expect(kpiValue(kpi({ key: "flood", unit: null, value: null }))).toBeNull();
    expect(kpiRank(flood, "property")).toBeNull();
    const road = kpi({ key: "aadt", unit: "vehicles", value: 25000, detail: "Cypress Lake Drive", note: "Estimate carried forward (no newer count)" });
    expect(kpiValue(road)).toBe("25,000");
    expect(kpiSub(road)).toBe("vehicles/day on Cypress Lake Drive · Estimate carried forward (no newer count)");
    expect(kpiValue(kpi({ unit: "places", value: 940 }))).toBe("940");
    const market = kpi({ key: "nearest_supermarket_mi", unit: "mi", value: 0.5, detail: "Publix" });
    expect(kpiValue(market)).toBe("0.5 mi");
    expect(kpiSub(market)).toBe("Publix");
    expect(kpiSub(kpi({ unit: "usd", value: 67968, index_vs_us: 84 }))).toBe("US index 84 (100 = US average)");
    expect(kpiRank(kpi({ rank: 3, of: 36, hypothetical: true }), "property")).toBe("Would rank 3 of 36 owned properties");
  });
});

describe("KPI change colour", () => {
  it("colours only significant changes on metrics with a good direction", () => {
    expect(kpiChange(kpi({ direction: "up", change: { value: 0.031, unit: "pct", since: "2015–2019", significant: true } }))).toEqual({
      text: "+3.1% since 2015–2019",
      tone: "good",
      direction: "up",
    });
    expect(kpiChange(kpi({ direction: "up", change: { value: -0.098, unit: "pct", since: "2024", significant: true } }))?.tone).toBe("bad");
    expect(kpiChange(kpi({ direction: "up", change: { value: 0.02, unit: "pct", since: "2024", significant: null } }))?.tone).toBe("neutral");
    const notSig = kpiChange(kpi({ direction: "up", change: { value: 0.02, unit: "pct", since: "2015–2019", significant: false } }));
    expect(notSig).toMatchObject({ tone: "neutral", text: "+2.0% since 2015–2019 (not significant)" });
    expect(kpiChange(kpi({ direction: null, change: { value: 0.5, unit: "pct", since: "x", significant: true } }))?.tone).toBe("neutral");
    expect(kpiChange(kpi({ change: null }))).toBeNull();
  });
});

describe("KPI rank", () => {
  it("prints N of M, the legacy percentile, or nothing for unranked figures", () => {
    expect(kpiRank(kpi({ rank: 4, of: 35 }), "property")).toBe("4 of 35");
    expect(kpiRank(kpi({ rank: 4, of: 35 }), "place")).toBe("Would rank 4 of 35 owned properties");
    expect(kpiRank(kpi({ percentile: 91, of: 34 }), "property")).toBe("Above 91% of 34 owned properties");
    expect(kpiRank(kpi({ ranked: false, rank: 1, of: 35 }), "property")).toBeNull();
    expect(kpiRank(kpi({}), "property")).toBeNull();
  });
  it("renders a labelled list of at most eight cards with a dash for missing values", () => {
    const many = Array.from({ length: 10 }, (_, i) => kpi({ key: `k${i}`, value: i === 0 ? null : i }));
    const html = renderToStaticMarkup(<KpiGrid kpis={many} mode="property" />);
    expect(html).toContain('aria-label="Key numbers"');
    expect(html.match(/class="kpi-card"/g)).toHaveLength(8);
    expect(html).toContain('<span class="sr-only">Unavailable</span>');
  });
});
