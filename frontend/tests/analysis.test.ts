import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deriveState,
  isBusy,
  newlyReady,
  POLL_GIVE_UP_MS,
  pollDelay,
  readyMessage,
  sectionRunState,
} from "../src/api/analysis";
import { createAnalysis, fetchAnalysis, resetRouteDetection } from "../src/api/hooks";
import { buildLegacyBundle, floodLabel, legacyKpis, legacyTakeaways, type LegacySummary } from "../src/api/legacyAnalysis";
import type { AnalysisBundle, SectionResult } from "../src/api/types";
import type { Area } from "../src/lib/format/area";
import type { Demographics } from "../src/lib/format/demographics";
import type { Location } from "../src/types";

const ID = "0b9f6c4e-6d1a-4c55-9b0e-2f5c7c1d9a10";
const location = (lat: number | null = 41.1384): Location => ({
  id: ID,
  seed_id: "P03",
  name: "1803 Post Road East",
  address: "1803 Post Road East",
  city: "Westport",
  state: "CT",
  status: "owned",
  asset_type: "shopping_center",
  ring_preset: "1/3/5",
  gla_sqft: null,
  notes: "",
  confirmed: true,
  confirmed_at: null,
  origin: "seed",
  source_url: "",
  source_context: {},
  version: 3,
  analysis_version: 2,
  current_revision: {
    id: "r",
    number: 2,
    lat,
    lon: lat === null ? null : -73.3008,
    method: "manual",
    matched_address: "",
    confirmed: true,
    context: {},
    created_at: "",
  },
  created_at: "",
  updated_at: "",
});
const ready = (data: unknown = {}): SectionResult => ({ status: "ready", reason: null, data: data as never, sources: [] });
const pending: SectionResult = { status: "pending", reason: null, data: null, sources: [] };

describe("pollDelay", () => {
  it("polls only while queued, running or partial", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 1500 })).toBe(1500);
    expect(pollDelay({ state: "queued", poll_after_ms: null })).toBe(3000);
    expect(pollDelay({ state: "partial", poll_after_ms: 3000 })).toBe(3000);
    for (const state of ["complete", "failed", "unplaced"] as const) expect(pollDelay({ state, poll_after_ms: 1500 })).toBe(false);
    expect(pollDelay(undefined)).toBe(false);
  });
  it("clamps the server's delay to 1.5–30 s", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 200 })).toBe(1500);
    expect(pollDelay({ state: "running", poll_after_ms: 120_000 })).toBe(30_000);
  });
  it("stops after 15 minutes of polling", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 3000 }, POLL_GIVE_UP_MS - 1)).toBe(3000);
    expect(pollDelay({ state: "running", poll_after_ms: 3000 }, POLL_GIVE_UP_MS)).toBe(false);
    expect(POLL_GIVE_UP_MS).toBe(900_000);
  });
});

describe("section state", () => {
  it("maps section status to what the shell shows", () => {
    expect(sectionRunState(ready())).toBe("ready");
    expect(sectionRunState({ ...ready(), data: null })).toBe("unavailable");
    expect(sectionRunState(pending)).toBe("loading");
    expect(sectionRunState({ ...pending, status: "running" })).toBe("loading");
    expect(sectionRunState({ status: "unavailable", reason: "Needs a map pin", data: null, sources: [] })).toBe("unavailable");
    expect(sectionRunState(undefined)).toBe("loading");
  });
  it("derives the overall state", () => {
    expect(deriveState(false, [ready()])).toBe("unplaced");
    expect(deriveState(true, [ready(), ready()])).toBe("complete");
    expect(deriveState(true, [ready(), pending])).toBe("partial");
    expect(deriveState(true, [pending, pending])).toBe("running");
    expect(deriveState(true, [{ status: "unavailable", reason: "x", data: null, sources: [] }])).toBe("failed");
    expect(isBusy("partial")).toBe(true);
    expect(isBusy("complete")).toBe(false);
  });
  it("announces sections that became ready, then completion", () => {
    const before = { sections: { businesses: pending, traffic: pending } } as unknown as AnalysisBundle;
    const after = { sections: { businesses: ready(), traffic: pending } } as unknown as AnalysisBundle;
    expect(newlyReady(before, after)).toEqual(["businesses"]);
    expect(readyMessage(["businesses"], false)).toBe("Retail landscape is ready.");
    expect(readyMessage(["traffic", "hazards"], false)).toBe("Access & traffic and Risk are ready.");
    expect(readyMessage([], true)).toBe("Analysis complete.");
    expect(readyMessage([], false)).toBe("");
  });
});

const demographics: Demographics = {
  status: "available",
  ring_preset: "1/3/5",
  acs_year: 2024,
  data_period: "ACS 2020–2024",
  computed_at: "2026-11-20T00:00:00Z",
  pin: { lat: 41.1384, lon: -73.3008, revision: "r" },
  rings: [
    {
      radius_miles: 3,
      metrics: {
        population: { metric_id: "MET-01", value: 84000, moe: 2000, reliability: "high", reason: null, unit: "people", label: null },
        median_household_income: {
          metric_id: "MET-03",
          value: 200000,
          moe: null,
          reliability: "high",
          reason: null,
          unit: "usd",
          label: null,
          open_ended: true,
          display: "≥ $200,000",
        },
      },
      method: { apportionment: "", blocks_inside: 1, block_groups: 1, land_area_weighted_block_groups: 0, moe_formula: "" },
      trends: { population_change: { metric_id: "MET-06", value: 0.031, significant: true, period: "2015–2019 → 2020–2024" } },
    },
  ],
  sources: [{ id: "SRC-03", name: "ACS", period: "ACS 2020–2024", url: "https://www.census.gov/" }],
  trend_baseline: { acs_year: 2019, cpi_ratio: 1.2 },
  caveats: [],
};
const area: Area = {
  placed: true,
  sections: {
    economy: { status: "not_computed", reason: "NOT_COMPUTED" },
    traffic: {
      status: "available",
      data: {
        radius_m: 250,
        year: 2025,
        note: "",
        roads: [
          { label: "US 1", aadt: 19000, year: 2025, road_class: null, lanes: null, prior_year: 2024, change_pct: -0.05, reason: null, count_year: 2024 },
        ],
      },
      sources: [{ id: "SRC-10", name: "HPMS", url: "", period: "2025", retrieved_at: "" }],
      computed_at: "2026-11-20T00:00:00Z",
    },
    hazards: {
      status: "available",
      data: {
        flood_at_pin: { zone: "AE", sfha: true, in_sfha: true, bfe_ft: 9, reason: null },
        flood_nearby: { reason: null },
        nri: { reason: null },
        concerns: [],
        disclaimer: "",
      },
      sources: [],
    },
    businesses: { status: "unavailable", reason: "SOURCE_ERROR", data: { reason: "SOURCE_ERROR" } as never },
    jobs: { status: "not_computed", reason: "STALE" },
  },
};
const summary: LegacySummary = {
  portfolio_size: 35,
  min_portfolio: 5,
  benchmark_ready: true,
  metrics: [
    { key: "population", label: "Population", unit: "people", direction: "up", value: 84000, period: null, source: "SRC-03", percentile: 91, n: 34 },
  ],
  strengths: [{ text: "Population within 3 miles: 84,000, better than 91% of your 34 properties", metric: "population", source: "SRC-03", period: "ACS 2020–2024" }],
  concerns: [{ text: "Inside a FEMA high-risk flood zone", metric: "hazards", source: "SRC-11", period: null }],
  signals: [],
  note: "",
};

describe("legacy bundle adapter", () => {
  const bundle = buildLegacyBundle(location(), demographics, area, summary);
  it("maps sections: available → ready, not yet computed → pending, failures → unavailable with a reason", () => {
    expect(bundle.sections.demographics.status).toBe("ready");
    expect(bundle.sections.demographics.trends).toBe("ready");
    expect(bundle.sections.traffic.status).toBe("ready");
    expect(bundle.sections.economy.status).toBe("pending");
    expect(bundle.sections.jobs.status).toBe("pending");
    expect(bundle.sections.businesses).toMatchObject({ status: "unavailable", reason: "SOURCE_ERROR", data: null });
    expect(bundle.analysis.state).toBe("partial");
    expect(bundle.analysis.poll_after_ms).toBe(3000);
    expect(bundle.location.kind).toBe("property");
    expect(bundle.legacy).toBe(true);
  });
  it("builds KPIs in the fixed order with real values only", () => {
    const kpis = legacyKpis(bundle.sections, summary);
    expect(kpis.map((k) => k.key)).toEqual([
      "population",
      "median_household_income",
      "households",
      "jobs",
      "aadt",
      "retail_1mi",
      "nearest_supermarket",
      "flood",
    ]);
    expect(kpis[0]).toMatchObject({ value: 84000, percentile: 91, of: 34, rank: null, change: { value: 0.031, significant: true } });
    expect(kpis[1]).toMatchObject({ value: 200000, display: "≥ $200,000" });
    expect(kpis[2].value).toBeNull(); // households missing → null, never 0
    expect(kpis[3].value).toBeNull(); // jobs still pending
    expect(kpis[4]).toMatchObject({ value: 19000, detail: "US 1", change: { value: -0.05, since: "2024" } });
    expect(kpis[0].change?.since).toBe("2015–2019");
    expect(kpis[7]).toMatchObject({ display: "Inside zone AE", detail: "Base flood elevation 9 ft", ranked: false });
  });
  it("turns the flood result into a risk badge and labels", () => {
    expect(bundle.risk_badges).toEqual([{ kind: "flood", label: "Inside FEMA zone AE", source: "SRC-11" }]);
    expect(floodLabel({ zone: "X", sfha: false, reason: null })).toBe("Outside high-risk zones (zone X)");
    expect(floodLabel({ reason: "NOT_COVERED" })).toBeNull();
  });
  it("lists concerns before strengths, at most five", () => {
    const t = legacyTakeaways(summary);
    expect(t.map((x) => x.tone)).toEqual(["caution", "positive"]);
    expect(t[0].section).toBe("risk");
    expect(t[1].section).toBe("trade-area");
    expect(legacyTakeaways(null)).toEqual([]);
  });
  it("marks every section unavailable for an unplaced record", () => {
    const unplaced = buildLegacyBundle(location(null), demographics, area, null);
    expect(unplaced.analysis.state).toBe("unplaced");
    expect(Object.values(unplaced.sections).every((s) => s.status === "unavailable")).toBe(true);
    expect(unplaced.analysis.poll_after_ms).toBeNull();
  });
});

describe("bundle endpoint detection", () => {
  beforeEach(() => {
    resetRouteDetection();
    vi.stubGlobal("document", { querySelector: () => ({ content: "csrf" }) });
  });
  afterEach(() => vi.unstubAllGlobals());
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  it("uses the bundle when the server has it", async () => {
    const bundle = {
      location: location(),
      analysis: { state: "complete" },
      sections: {},
      kpis: [{ key: "population", label: "People", value: 1, unit: "people" }],
      takeaways: [{ text: "t", tone: "neutral", section: "overview", source: null, period: null }],
    };
    const fetcher = vi.fn().mockResolvedValue(json(bundle));
    vi.stubGlobal("fetch", fetcher);
    const result = await fetchAnalysis(ID);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/locations/${ID}/analysis/`);
    expect(result.kpis).toHaveLength(1);
    expect(result.legacy).toBeUndefined();
  });
  it("fills KPIs and takeaways from the summary while the bundle has none (before B6b)", async () => {
    const sections = buildLegacyBundle(location(), demographics, area, null).sections;
    const bundle = { location: location(), analysis: { state: "partial" }, sections, kpis: [], takeaways: [] };
    const fetcher = vi.fn(async (path: string) => (path.endsWith("/summary/") ? json(summary) : json(bundle)));
    vi.stubGlobal("fetch", fetcher);
    const result = await fetchAnalysis(ID);
    expect(fetcher.mock.calls.map(([p]) => p)).toEqual([`/api/locations/${ID}/analysis/`, `/api/locations/${ID}/summary/`]);
    expect(result.kpis[0]).toMatchObject({ key: "population", value: 84000, percentile: 91 });
    expect(result.takeaways.map((t) => t.tone)).toEqual(["caution", "positive"]);
    expect(result.portfolio).toMatchObject({ size: 35, ready: true });
  });
  it("returns B5's 503 body (geocoder down) instead of throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ location: location(), geocode: { status: "unavailable" }, next: "place_pin" }, 503)),
    );
    const result = await createAnalysis({ address: "1 Main St, Anywhere, CT" });
    expect(result).toMatchObject({ geocode: { status: "unavailable" }, next: "place_pin" });
  });
  it("falls back to the legacy endpoints on a bare 404 and remembers it", async () => {
    const fetcher = vi.fn(async (path: string) => {
      if (path.endsWith("/analysis/")) return new Response("<h1>Not Found</h1>", { status: 404 });
      if (path.endsWith("/demographics/")) return json(demographics);
      if (path.endsWith("/area/")) return json(area);
      if (path.endsWith("/summary/")) return json(summary);
      return json(location());
    });
    vi.stubGlobal("fetch", fetcher);
    expect((await fetchAnalysis(ID)).legacy).toBe(true);
    expect((await fetchAnalysis(ID)).legacy).toBe(true);
    expect(fetcher.mock.calls.filter(([p]) => String(p).endsWith("/analysis/"))).toHaveLength(1);
  });
  it("treats a 404 with a JSON detail as an unknown property", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "No Location matches the given query." }, 404)));
    await expect(fetchAnalysis(ID)).rejects.toMatchObject({ status: 404 });
  });
  it("creates new places through /api/analyses/, or the screens API before B5", async () => {
    const fetcher = vi.fn(async (path: string) =>
      path === "/api/analyses/"
        ? new Response("", { status: 404 })
        : json({ location: location(), geocode_status: "ambiguous", jobs: [] }, 201),
    );
    vi.stubGlobal("fetch", fetcher);
    const result = await createAnalysis({ address: "1803 Post Road East, Westport, CT" });
    expect(result.geocode?.status).toBe("ambiguous");
    expect(result.next).toBe("place_pin");
    expect(fetcher.mock.calls[1][0]).toBe("/api/screens/");
    await expect(createAnalysis({ lat: 41, lon: -73 })).rejects.toMatchObject({ status: 400 });
  });
});
