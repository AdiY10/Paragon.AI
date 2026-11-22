/**
 * TEMPORARY (WI-5 → removed once B3b's GET /api/locations/<id>/analysis/ is on every server):
 * assembles the PART C bundle from /demographics/, /area/ and /summary/. Analyses start on their
 * own (B3a), so this only reads; it never POSTs a compute request.
 */
import { releaseLabel, type Area, type Flood, type Section } from "../lib/format/area";
import { dateLabel } from "../lib/format/dates";
import type { Demographics, Ring } from "../lib/format/demographics";
import type { Location } from "../types";
import { deriveState } from "./analysis";
import { api } from "./client";
import type {
  AnalysisBundle,
  AnalysisSignal,
  Kpi,
  RiskBadge,
  SectionKey,
  SectionResult,
  Sections,
  SourceRef,
  Takeaway,
} from "./types";

interface SummaryMetric {
  key: string;
  label: string;
  unit: string;
  direction: "up" | "down";
  value: number | null;
  period: string | null;
  source: string | null;
  percentile: number | null;
  n: number;
}
interface SummaryItem {
  text: string;
  metric: string;
  source: string | null;
  period: string | null;
}
export interface LegacySummary {
  portfolio_size: number;
  min_portfolio: number;
  benchmark_ready: boolean;
  metrics: SummaryMetric[];
  strengths: SummaryItem[];
  concerns: SummaryItem[];
  signals: AnalysisSignal[];
  note: string;
}

const NOT_YET = new Set(["NOT_COMPUTED", "STALE"]);
const reasonFor = (code: string | null | undefined) =>
  code === "NOT_PROVIDED" ? "Needs a map pin" : code ? code : "Not available for this location";

function areaSection<K extends Exclude<SectionKey, "demographics">>(s: Section<unknown> | undefined): SectionResult<K> {
  if (!s) return { status: "pending", reason: null, data: null, sources: [] };
  if (s.status === "available")
    return {
      status: "ready",
      reason: null,
      data: (s.data ?? null) as SectionResult<K>["data"],
      sources: s.sources ?? [],
      computed_at: s.computed_at ?? null,
      stale: !!s.stale,
    };
  if (s.status === "not_computed" && NOT_YET.has(s.reason ?? "NOT_COMPUTED"))
    return { status: "pending", reason: null, data: null, sources: [] };
  return {
    status: "unavailable",
    reason: reasonFor(s.reason ?? s.data?.reason),
    data: null,
    sources: s.sources ?? [],
    computed_at: s.computed_at ?? null,
  };
}

function demographicsSection(d: Demographics): SectionResult<"demographics"> {
  if (d.status === "available") {
    const { status: _status, ...data } = d;
    const hasTrends = d.rings.some((r) => r.trends && Object.keys(r.trends).length);
    return {
      status: "ready",
      reason: null,
      trends: hasTrends ? "ready" : "unavailable",
      data,
      sources: d.sources.map((s) => ({ ...s, retrieved_at: s.retrieved_at ?? "" })),
      computed_at: d.computed_at,
    };
  }
  if (NOT_YET.has(d.reason)) return { status: "pending", reason: null, data: null, sources: [] };
  return { status: "unavailable", reason: d.message || reasonFor(d.reason), data: null, sources: [] };
}

const ring3 = (rings: Ring[] | undefined) => rings?.find((r) => r.radius_miles === 3);

/** Inside / near / outside a FEMA high-risk zone, as a short label. */
export function floodLabel(f: Flood | undefined): string | null {
  if (!f || f.reason || !f.zone) return null;
  const inside = f.in_sfha ?? f.sfha;
  if (inside) return `Inside FEMA zone ${f.zone}${f.bfe_ft != null ? ` (base flood elevation ${f.bfe_ft} ft)` : ""}`;
  return `Outside high-risk zones (zone ${f.zone})`;
}

/** Tile-sized flood status: "Inside zone AE" / "Outside high-risk zones". */
export function floodShortLabel(f: Flood | undefined): string | null {
  if (!f || f.reason || !f.zone) return null;
  return (f.in_sfha ?? f.sfha) ? `Inside zone ${f.zone}` : "Outside high-risk zones";
}

/** KPI set in the fixed B6b order, built from the section data plus summary percentiles. */
export function legacyKpis(sections: Sections, summary: LegacySummary | null): Kpi[] {
  const metric = (key: string) => summary?.metrics.find((m) => m.key === key);
  const ranking = (key: string) => {
    const m = metric(key);
    // Legacy summaries give a percentile against the *other* owned properties (n), not a rank.
    return m && m.percentile !== null ? { percentile: m.percentile, of: m.n, rank: null } : { percentile: null, of: null };
  };
  const demo = sections.demographics.data;
  const r3 = ring3(demo?.rings);
  const m3 = (key: string) => r3?.metrics[key];
  const popTrend = r3?.trends?.population_change;
  const jobs = sections.jobs.data?.rings.find((r) => r.radius_miles === 3);
  const road = sections.traffic.data?.roads[0];
  const biz = sections.businesses.data;
  const flood = sections.hazards.data?.flood_at_pin;
  const acs = demo ? demo.data_period : null;
  return [
    {
      key: "population",
      label: "People within 3 mi",
      value: m3("population")?.value ?? null,
      unit: "people",
      direction: "up",
      period: acs,
      source: "SRC-03",
      ranked: true,
      ...ranking("population"),
      change:
        popTrend && popTrend.value !== null
          ? {
              value: popTrend.value,
              unit: "pct",
              // "2015–2019 → 2020–2024": the change is since the earlier period.
              since: (popTrend.period ?? demo?.trend_baseline?.acs_year?.toString() ?? "").split("→")[0].trim(),
              significant: popTrend.significant ?? null,
            }
          : null,
    },
    {
      key: "median_household_income",
      label: "Median household income (3 mi)",
      value: m3("median_household_income")?.value ?? null,
      display: m3("median_household_income")?.display ?? null,
      unit: "usd",
      direction: "up",
      period: acs,
      source: "SRC-03",
      ranked: true,
      ...ranking("median_household_income"),
    },
    {
      key: "households",
      label: "Households within 3 mi",
      value: m3("households")?.value ?? null,
      unit: "households",
      direction: "up",
      period: acs,
      source: "SRC-03",
      ranked: true,
      ...ranking("households"),
    },
    {
      key: "jobs",
      label: "Jobs within 3 mi",
      value: jobs?.total ?? null,
      unit: "people",
      direction: "up",
      period: sections.jobs.data ? `LODES ${sections.jobs.data.year}` : null,
      source: "SRC-05",
      ranked: true,
      ...ranking("jobs"),
      change:
        jobs && jobs.change_pct !== null && sections.jobs.data?.prior_year
          ? { value: jobs.change_pct, unit: "pct", since: String(sections.jobs.data.prior_year), significant: null }
          : null,
    },
    {
      key: "aadt",
      label: "Main-road traffic",
      value: road?.aadt ?? null,
      unit: "per_day",
      detail: road ? road.label : null,
      direction: "up",
      period: road ? `${road.count_year ?? road.year}` : null,
      source: "SRC-10",
      ranked: true,
      ...ranking("aadt"),
      change:
        road && road.change_pct !== null && road.prior_year
          ? { value: road.change_pct, unit: "pct", since: String(road.prior_year), significant: null }
          : null,
    },
    {
      key: "retail_1mi",
      label: "Retail & services within 1 mi",
      value: biz?.retail_and_services_total?.["1mi"] ?? null,
      unit: "count",
      period: biz ? releaseLabel(biz.release) : null,
      source: "SRC-13",
      ranked: false,
      percentile: null,
      of: null,
    },
    {
      key: "nearest_supermarket",
      label: "Nearest supermarket",
      value: biz?.nearest_supermarket?.distance_mi ?? null,
      display: biz?.nearest_supermarket ? biz.nearest_supermarket.name ?? biz.nearest_supermarket.brand : null,
      unit: "mi",
      period: biz ? releaseLabel(biz.release) : null,
      source: "SRC-13",
      ranked: false,
      percentile: null,
      of: null,
    },
    {
      key: "flood",
      label: "Flood status",
      value: null,
      display: floodShortLabel(flood),
      detail: flood && !flood.reason && flood.bfe_ft != null ? `Base flood elevation ${flood.bfe_ft} ft` : null,
      unit: "text",
      period: flood?.checked ? dateLabel(flood.checked) : null,
      source: "SRC-11",
      ranked: false,
      percentile: null,
      of: null,
    },
  ];
}

const SECTION_OF_METRIC: Record<string, string> = {
  population: "trade-area",
  households: "trade-area",
  median_household_income: "trade-area",
  mean_household_income: "trade-area",
  population_change: "trade-area",
  real_income_change: "trade-area",
  jobs: "daytime",
  jobs_change: "daytime",
  private_jobs_yoy: "market",
  retail_jobs_yoy: "market",
  unemployment_change: "market",
  permits_change: "market",
  aadt: "access",
  hazards: "risk",
  signal: "overview",
};

/** ≤5 deterministic takeaways from the summary's strengths and concerns (concerns first). */
export function legacyTakeaways(summary: LegacySummary | null): Takeaway[] {
  if (!summary) return [];
  const pick = (items: SummaryItem[], tone: Takeaway["tone"]) =>
    items.map((i) => ({
      text: i.text,
      tone,
      section: SECTION_OF_METRIC[i.metric] ?? "overview",
      source: i.source,
      period: i.period,
    }));
  return [...pick(summary.concerns, "caution"), ...pick(summary.strengths, "positive")].slice(0, 5);
}

function uniqueSources(sections: Sections): SourceRef[] {
  const seen = new Map<string, SourceRef>();
  for (const s of Object.values(sections)) for (const src of s.sources ?? []) seen.set(`${src.id}|${src.period}`, src);
  return [...seen.values()];
}

export function buildLegacyBundle(
  location: Location,
  demographics: Demographics,
  area: Area,
  summary: LegacySummary | null,
): AnalysisBundle {
  const placed = location.current_revision.lat !== null && location.current_revision.lon !== null;
  const sections: Sections = {
    demographics: demographicsSection(demographics),
    economy: areaSection<"economy">(area.sections.economy),
    traffic: areaSection<"traffic">(area.sections.traffic),
    hazards: areaSection<"hazards">(area.sections.hazards),
    businesses: areaSection<"businesses">(area.sections.businesses),
    jobs: areaSection<"jobs">(area.sections.jobs),
  };
  if (!placed)
    for (const key of Object.keys(sections) as SectionKey[])
      sections[key] = { status: "unavailable", reason: "Needs a map pin", data: null, sources: [] } as never;
  const state = deriveState(placed, Object.values(sections));
  const flood = sections.hazards.data?.flood_at_pin;
  const risk: RiskBadge[] =
    flood && !flood.reason && (flood.in_sfha ?? flood.sfha) && flood.zone
      ? [{ kind: "flood", label: `Inside FEMA zone ${flood.zone}`, source: "SRC-11" }]
      : [];
  return {
    location: {
      ...location,
      kind: location.screening ? "place" : "property",
      display_label: null,
      kept: false,
      expires_at: null,
    },
    analysis: {
      state,
      analysis_version: location.analysis_version,
      job: null,
      next_retry_at: null,
      poll_after_ms: state === "queued" || state === "running" || state === "partial" ? 3000 : null,
    },
    sections,
    kpis: legacyKpis(sections, summary),
    takeaways: legacyTakeaways(summary),
    signals: summary?.signals ?? [],
    risk_badges: risk,
    tenants: [],
    sources: uniqueSources(sections),
    portfolio: summary
      ? { size: summary.portfolio_size, min: summary.min_portfolio, ready: summary.benchmark_ready, note: summary.note }
      : undefined,
    legacy: true,
  };
}

export async function fetchLegacyBundle(id: string): Promise<AnalysisBundle> {
  const base = `/api/locations/${id}/`;
  const location = await api<Location>(base);
  const [demographics, area, summary] = await Promise.all([
    api<Demographics>(base + "demographics/"),
    api<Area>(base + "area/"),
    api<LegacySummary>(base + "summary/").catch(() => null),
  ]);
  return buildLegacyBundle(location, demographics, area, summary);
}
