import { describe, expect, it } from "vitest";
import type { SignalGroup } from "../src/api/types";
import { arrange, DEFAULT_LEVELS, filterGroups, levelsParam, parseLevels } from "../src/features/alerts/grouping";

let n = 0;
const loc = (id: string, name: string) => ({ id, name, city: "", state: "CT" });
const group = (p: Partial<SignalGroup>): SignalGroup => ({
  key: `k${++n}`,
  rule_id: "SIG-08",
  title: `Alert ${n}`,
  severity: "Watch",
  category: "Access",
  why: "",
  next_step: null,
  evidence: {},
  period: null,
  source: null,
  status: "active",
  locations: [loc("a", "Alpha")],
  signal_ids: [`s${n}`],
  ...p,
});

describe("alert levels in the URL", () => {
  it("defaults to High and Watch", () => {
    expect(parseLevels(null)).toEqual(DEFAULT_LEVELS);
    expect(parseLevels("nonsense")).toEqual(["High", "Watch"]);
    expect(parseLevels("High,FYI")).toEqual(["High", "FYI"]);
    expect(levelsParam(["Watch", "High"])).toBe("");
    expect(levelsParam(["High", "Watch", "FYI"])).toBe("High,Watch,FYI");
  });
});

describe("filter and arrange", () => {
  const high = group({ severity: "High", locations: [loc("b", "Bravo")] });
  const watchA = group({ locations: [loc("a", "Alpha")], category: "Retail" });
  const county = group({ rule_id: "SIG-15", category: "Market", locations: [loc("a", "Alpha"), loc("b", "Bravo")] });
  const fyi = group({ severity: "FYI", locations: [loc("c", "Charlie")] });
  const all = [watchA, county, high, fyi];
  it("filters by level, category and property (shared alerts match any of their properties)", () => {
    expect(filterGroups(all, { levels: DEFAULT_LEVELS })).toEqual([watchA, county, high]);
    expect(filterGroups(all, { levels: ["FYI"] })).toEqual([fyi]);
    expect(filterGroups(all, { levels: DEFAULT_LEVELS, category: "Retail" })).toEqual([watchA]);
    expect(filterGroups(all, { levels: DEFAULT_LEVELS, property: "b" })).toEqual([county, high]);
  });
  it("lists shared alerts once and orders properties worst first", () => {
    const { shared, byProperty } = arrange(filterGroups(all, { levels: DEFAULT_LEVELS }));
    expect(shared).toEqual([county]);
    expect(byProperty.map((b) => b.location.name)).toEqual(["Bravo", "Alpha"]);
    expect(byProperty[1].groups).toEqual([watchA]);
  });
});
