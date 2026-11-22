/**
 * PART C contract types (docs/REDESIGN_PLAN.md). The section `data` shapes are the existing
 * area/demographics payloads, so the analysis sections render the same fields from either source.
 */
import type { Businesses, Economy, Hazards, Jobs, SourceRef, Traffic } from "../lib/format/area";
import type { Demographics } from "../lib/format/demographics";
import type { Location, Session, Source, Page } from "../types";

export type { Location, Session, Source, Page, SourceRef };

export type AnalysisState = "unplaced" | "queued" | "running" | "partial" | "complete" | "failed";
export type SectionKey = "demographics" | "economy" | "traffic" | "hazards" | "businesses" | "jobs";
export const SECTION_KEYS: SectionKey[] = ["demographics", "economy", "traffic", "hazards", "businesses", "jobs"];
export type SectionStatus = "ready" | "running" | "pending" | "unavailable";

export type DemographicsData = Omit<Extract<Demographics, { status: "available" }>, "status">;
export interface SectionDataMap {
  demographics: DemographicsData;
  economy: Economy;
  traffic: Traffic;
  hazards: Hazards;
  businesses: Businesses;
  jobs: Jobs;
}
export interface SectionResult<K extends SectionKey = SectionKey> {
  status: SectionStatus;
  /** Plain-language reason when unavailable (or a reason code the UI turns into text). */
  reason: string | null;
  /** Demographics only: whether the 2015–19 comparison is in. */
  trends?: "ready" | "running" | "pending" | "unavailable";
  stale?: boolean;
  computed_at?: string | null;
  data: SectionDataMap[K] | null;
  sources: SourceRef[];
}
export type Sections = { [K in SectionKey]: SectionResult<K> };

export interface Kpi {
  key: string;
  label: string;
  value: number | null;
  unit: "people" | "households" | "usd" | "pct" | "pts" | "count" | "per_day" | "mi" | "text" | string;
  /** Pre-formatted value for text KPIs (e.g. "Publix", "Inside zone AE"). */
  display?: string | null;
  detail?: string | null;
  rank?: number | null;
  of?: number | null;
  percentile?: number | null;
  direction?: "up" | "down" | null;
  change?: { value: number; unit: "pct" | "pts"; since: string; significant: boolean | null } | null;
  period?: string | null;
  source?: string | null;
  /** Flood status and similar badges are never ranked. */
  ranked?: boolean;
}
export interface Takeaway {
  text: string;
  tone: "positive" | "neutral" | "caution";
  section: string;
  source: string | null;
  period: string | null;
}
export interface RiskBadge {
  kind: string;
  label: string;
  source: string;
}
export interface AnalysisSignal {
  id: string;
  rule_id: string;
  title: string;
  severity: "High" | "Watch" | "FYI";
  why: string;
  next_step?: string | null;
  detected_at?: string;
  source?: string | null;
  period?: string | null;
  evidence?: Record<string, unknown>;
}
export interface AnalysisInfo {
  state: AnalysisState;
  analysis_version: number;
  job: { id: string; status: string; started_at: string | null; attempt: number } | null;
  next_retry_at: string | null;
  poll_after_ms: number | null;
}
export type AnalysisLocation = Location & {
  kind: "property" | "place";
  display_label?: string | null;
  kept?: boolean;
  expires_at?: string | null;
};
export interface AnalysisBundle {
  location: AnalysisLocation;
  analysis: AnalysisInfo;
  sections: Sections;
  kpis: Kpi[];
  takeaways: Takeaway[];
  signals: AnalysisSignal[];
  risk_badges: RiskBadge[];
  tenants: unknown[];
  sources: SourceRef[];
  /** Portfolio comparison context (legacy summary): rankable when ≥ min_portfolio. */
  portfolio?: { size: number; min: number; ready: boolean; note: string };
  /** True when the client assembled this from the pre-bundle endpoints (WI-5 adapter). */
  legacy?: boolean;
}

/** GET /api/analyses/ row (B5). */
export interface AnalysisListItem {
  id: string;
  name: string;
  display_label?: string | null;
  address: string;
  lat: number | null;
  lon: number | null;
  created_at: string;
  kept: boolean;
  expires_at: string | null;
  state: AnalysisState;
  key_numbers?: Location["key_numbers"];
}
export type CreateAnalysisBody = { address: string; name?: string } | { lat: number; lon: number; label?: string };
export interface CreateAnalysisResponse {
  location: Location;
  geocode?: {
    status: "matched" | "ambiguous" | "no_match" | "unavailable";
    matched_address?: string;
    lookup_id?: string;
    candidates?: { index: number; matched_address: string; lat: number; lon: number }[];
  };
  analysis?: { state: AnalysisState; job_id?: string };
  next?: "place_pin";
}

/** GET /api/signals/ (B7a): grouped alerts plus the old flat list. */
export interface SignalGroup {
  key: string;
  rule_id: string;
  title: string;
  severity: "High" | "Watch" | "FYI";
  category: string;
  why: string;
  next_step: string | null;
  evidence: Record<string, unknown>;
  period: string | null;
  source: string | null;
  status: string;
  locations: { id: string; name: string; city: string; state: string }[];
  signal_ids: string[];
}
export interface SignalsResponse {
  groups: SignalGroup[];
  results: (AnalysisSignal & {
    status: string;
    category: string;
    direction?: string;
    changed_at?: string;
    reviewed?: boolean;
    reviewed_at?: string | null;
    review_note?: string;
    feedback?: string | null;
    location: { id: string; name: string; city: string; state: string };
  })[];
}
