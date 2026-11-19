/** Types and pure formatting for /api/locations/<id>/area/ (economy, traffic, hazards). */
import { reasonText } from "./demographics";

export interface SourceRef {
  id: string;
  name: string;
  url: string;
  period: string;
  retrieved_at: string;
}
export interface Section<T> {
  status: "available" | "unavailable" | "not_computed";
  reason?: string;
  data?: T & { reason?: string };
  sources?: SourceRef[];
  computed_at?: string;
}
export interface Industry {
  label: string;
  value: number | null;
  establishments?: number;
  avg_weekly_wage?: number;
  yoy_pct?: number | null;
  yoy_reason?: string | null;
  reason: string | null;
}
export interface Economy {
  county: { fips: string; name: string };
  employment: {
    period?: string;
    private?: Industry;
    retail?: Industry;
    reason?: string | null;
  };
  unemployment: {
    rate?: number;
    period?: string;
    preliminary?: boolean;
    prior_rate?: number;
    change_pts?: number | null;
    change_reason?: string | null;
    reason?: string | null;
  };
  permits: {
    value: number | null;
    prior?: number;
    change?: number;
    change_pct?: number | null;
    period?: string;
    prior_period?: string;
    reason: string | null;
  };
}
export interface Road {
  label: string;
  aadt: number;
  year: number;
  road_class: string | null;
  lanes: number | null;
  prior_aadt?: number | null;
  prior_year?: number;
  change_pct: number | null;
  reason: string | null;
}
export interface Traffic {
  radius_m: number;
  year: number;
  roads: Road[];
  note: string;
}
export interface Flood {
  zone?: string | null;
  subtype?: string | null;
  sfha?: boolean;
  bfe_ft?: number | null;
  dfirm_id?: string;
  risk?: "minimal" | "moderate" | "high" | "high_coastal";
  checked?: string;
  reason: string | null;
}
export interface Hazards {
  flood_at_pin: Flood;
  flood_nearby: Flood;
  nri: {
    rating?: string | null;
    percentile?: number | null;
    version?: string;
    tract?: string;
    top_hazards?: { hazard: string; rating: string }[];
    concern?: boolean;
    reason: string | null;
  };
  concerns: string[];
  disclaimer: string;
}
export interface Place {
  id: string;
  name: string | null;
  brand: string | null;
  category: string | null;
  group: string;
  distance_mi: number;
  status: string | null;
  confidence: number | null;
  grocery: boolean;
  severity?: "High" | "Watch" | "FYI";
  evidence?: string;
  tenant_match?: boolean;
}
export interface Businesses {
  release: string;
  prior_release: string | null;
  counts: Record<string, Record<string, number>>;
  retail_and_services_total: Record<string, number>;
  anchors: Place[];
  nearest_supermarket: Place | null;
  closed_within_1mi: number;
  changes: {
    closures: Place[];
    openings: Place[];
    total_closures?: number;
    total_openings?: number;
    broad_data_change?: boolean | null;
    tenants_checked?: number;
    reason: string | null;
  };
}
export interface Area {
  placed: boolean;
  sections: {
    economy: Section<Economy>;
    traffic: Section<Traffic>;
    hazards: Section<Hazards>;
    businesses: Section<Businesses>;
  };
}

const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
export const count = (n: number | null | undefined) =>
  n === null || n === undefined ? "Unavailable" : int.format(n);
export const money = (n: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);

/** Signed percent with a true minus sign; null -> reason text, never 0. */
export function signedPct(
  value: number | null | undefined,
  reason?: string | null,
): string {
  if (value === null || value === undefined) return reasonText(reason);
  const pct = value * 100;
  const sign = pct > 0.05 ? "+" : pct < -0.05 ? "−" : "";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}
export function signedPts(value: number | null | undefined): string {
  if (value === null || value === undefined) return "No comparison";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}${Math.abs(value).toFixed(1)} pts`;
}
export const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

/** "2026-09" -> "Sep 2026"; "12 months to 2026-09" keeps its prefix. */
export function monthLabel(text: string | undefined): string {
  if (!text) return "";
  return text.replace(/(\d{4})-(\d{2})/, (_, y: string, m: string) =>
    new Date(Number(y), Number(m) - 1, 1).toLocaleString("en-US", {
      month: "short",
      year: "numeric",
    }),
  );
}

export function floodHeadline(f: Flood): string {
  if (f.reason || !f.zone) return reasonText(f.reason ?? "NOT_COVERED");
  if (f.sfha) return `Zone ${f.zone} · Special Flood Hazard Area`;
  if (f.risk === "moderate") return `Zone ${f.zone} · moderate (0.2% annual chance)`;
  return `Zone ${f.zone} · minimal flood hazard`;
}

export const floodTone = (f: Flood) =>
  f.sfha ? "red" : f.risk === "moderate" ? "amber" : "neutral";

export const miles = (d: number) => `${d.toFixed(1)} mi`;
export const placeName = (p: Place) => p.name ?? p.brand ?? "Unnamed place";
export function releaseLabel(release: string | null | undefined) {
  if (!release) return "";
  const [y, m, d] = release.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", year: "numeric" });
}
