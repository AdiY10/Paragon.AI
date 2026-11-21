/** Plain-English evidence for each alert rule and a short glossary (R2 item 20). */

type Ev = Record<string, unknown>;
const num = (v: unknown) => (typeof v === "number" ? v : null);
const MINUS = "−";

export function pct(v: unknown, digits = 1): string | null {
  const n = num(v);
  if (n === null) return null;
  const sign = n > 0 ? "+" : n < 0 ? MINUS : "";
  return `${sign}${Math.abs(n * 100).toFixed(digits)}%`;
}
const rate = (v: unknown) => (num(v) === null ? null : `${(num(v)! * 100).toFixed(1)}%`);
const count = (v: unknown) => (num(v) === null ? null : Math.round(num(v)!).toLocaleString("en-US"));
const pts = (v: unknown) => {
  const n = num(v);
  return n === null ? null : `${n > 0 ? "+" : n < 0 ? MINUS : ""}${Math.abs(n).toFixed(1)} points`;
};
const money = (v: unknown) => (num(v) === null ? null : `$${Math.round(num(v)!).toLocaleString("en-US")}`);
const miles = (v: unknown) => (num(v) === null ? null : `${num(v)!.toFixed(1)} miles from the pin`);
const metres = (v: unknown) => (num(v) === null ? null : `about ${num(v)} m from the pin`);
const text = (v: unknown) => (v === null || v === undefined || v === "" ? null : String(v));

const RULES: Record<string, (e: Ev) => [string, string | null][]> = {
  "SIG-01": (e) => [
    ["People within 3 miles now", count(e.current)],
    ["Five years earlier", count(e.baseline)],
    ["Alert threshold", pct(e.threshold, 0) && `a change of ${pct(e.threshold, 0)!.replace("+", "")} or more`],
  ],
  "SIG-02": (e) => [
    ["Average household income now", money(e.current)],
    ["Five years earlier, in today's dollars", money(e.baseline_inflation_adjusted)],
  ],
  "SIG-03": (e) => [
    ["Change in private-sector jobs", pct(e.value)],
    ["Private-sector jobs in the county", count(e.jobs)],
    ["Alert when below", pct(e.watch_at_or_below, 0)],
  ],
  "SIG-04": (e) => [
    ["Change in retail jobs", pct(e.value)],
    ["Alert when below", pct(e.watch_at_or_below, 0)],
  ],
  "SIG-05": (e) => [
    ["Unemployment rate (latest month)", rate(e.rate)],
    ["3-month average", rate(e.three_month_average)],
    ["A year earlier", rate(e.prior_rate)],
    ["Rise vs a year earlier", pts(e.change_pts)],
    ["Rose more than the state by", pts(e.more_than_state_pts)],
  ],
  "SIG-06": (e) => [
    ["Jobs located within 3 miles", count(e.current)],
    ["A year earlier", count(e.prior)],
  ],
  "SIG-07": (e) => [
    ["New homes permitted, last 12 months", count(e.current)],
    ["Previous 12 months", count(e.prior)],
  ],
  "SIG-08": (e) => [
    ["Vehicles per day now", count(e.aadt)],
    ["A year earlier", count(e.prior_aadt)],
  ],
  "SIG-09": (e) => [
    ["What the map data shows", text(e.evidence)],
    ["Distance", miles(e.distance_mi)],
    ["Type of business", text(e.category)?.replaceAll("_", " ") ?? null],
    ["Map data release", text(e.release)],
  ],
  "SIG-10": (e) => [
    ["Distance", miles(e.distance_mi)],
    ["Type of business", text(e.category)?.replaceAll("_", " ") ?? null],
    ["Map data release", text(e.release)],
  ],
  "SIG-11": (e) => [
    ["FEMA flood zone", text(e.zone)],
    ["Distance to the high-risk zone", metres(e.distance_m)],
    ["Base flood elevation", num(e.base_flood_elevation_ft) === null ? null : `${e.base_flood_elevation_ft} ft`],
    ["FEMA map panel", text(e.flood_map_panel)],
  ],
};

/** Labelled, formatted evidence rows; unknown rules fall back to readable key names. */
export function evidenceRows(ruleId: string, evidence: Ev): [string, string][] {
  const rule = RULES[ruleId];
  const rows = rule
    ? rule(evidence)
    : Object.entries(evidence)
        .filter(([k, v]) => k !== "source_link" && v !== null && typeof v !== "object")
        .map(([k, v]) => [k.replaceAll("_", " "), String(v)] as [string, string | null]);
  return rows.filter((r): r is [string, string] => r[1] !== null && r[1] !== "");
}

export const RULE_NAMES: Record<string, string> = {
  "SIG-01": "Population change",
  "SIG-02": "Household income change",
  "SIG-03": "County private jobs",
  "SIG-04": "County retail jobs",
  "SIG-05": "County unemployment",
  "SIG-06": "Jobs near the property",
  "SIG-07": "New housing permits",
  "SIG-08": "Traffic change",
  "SIG-09": "Possible closure nearby",
  "SIG-10": "New business nearby",
  "SIG-11": "Flood zone",
  "SIG-12": "Tenant filing (bankruptcy)",
  "SIG-13": "Tenant filing (closures or impairment)",
};

export const GLOSSARY: Record<string, string> = {
  ACS: "American Community Survey: the Census Bureau's yearly survey, published as 5-year averages for small areas.",
  LODES: "Census data on where people work, by census block.",
  HPMS: "The federal highway database states use to report traffic counts (vehicles per day).",
  NRI: "FEMA's National Risk Index: natural-hazard risk ratings by census tract.",
  "High-risk flood zone":
    "A FEMA Special Flood Hazard Area (zones A and V): a 1% or higher chance of flooding each year; flood insurance is usually required for mortgages.",
  CIK: "The SEC's identifier for a company that files reports.",
  CPI: "Consumer Price Index, used to compare incomes from different years in today's dollars.",
  QCEW: "Bureau of Labor Statistics count of jobs and wages by county, from employer tax records.",
  LAUS: "Bureau of Labor Statistics monthly unemployment estimates by county.",
};
