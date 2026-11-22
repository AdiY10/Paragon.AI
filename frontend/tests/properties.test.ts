import { describe, expect, it } from "vitest";
import { attentionCounts, attentionRank, filterProperties, sortProperties, sortValue } from "../src/lib/properties";
import type { Location } from "../src/types";

let n = 0;
function loc(partial: Partial<Location>): Location {
  n += 1;
  return {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    seed_id: null,
    name: `Property ${n}`,
    address: "",
    city: "",
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
    version: 1,
    analysis_version: 1,
    current_revision: {
      id: "r",
      number: 1,
      lat: 41,
      lon: -73,
      method: "manual",
      matched_address: "",
      confirmed: true,
      context: {},
      created_at: "",
    },
    created_at: "",
    updated_at: "",
    ...partial,
  };
}

const norwalk = loc({ name: "Norwalk Plaza", city: "Norwalk", state: "CT", attention: "Watch", address: "444 Westport Ave",
  key_numbers: { population: 84000, median_household_income: 98000, aadt: 21000, flood: "none", active_alerts: 1 } });
const cypress = loc({ name: "Cypress Lake Center", city: "Fort Myers", state: "FL", attention: "High",
  key_numbers: { population: 67312, flood: "inside", nearest_supermarket: { name: "Publix", distance_mi: 0.5 }, active_alerts: 2 } });
const kingston = loc({ name: "Kingston Commons", city: "Kingston", state: "NY",
  key_numbers: { aadt: 22523, flood: "near", nearest_supermarket: { name: "ShopRite", distance_mi: 1.2 }, active_alerts: 0 } });
const empty = loc({ name: "Bareburger", city: "Mount Kisco", state: "NY", key_numbers: {} });
const candidate = loc({ name: "Candidate", status: "candidate" });
const all = [norwalk, cypress, kingston, empty, candidate];

describe("filterProperties", () => {
  it("keeps owned properties only", () => {
    expect(filterProperties(all, {})).toHaveLength(4);
  });
  it("filters by state and attention (missing attention is Clear)", () => {
    expect(filterProperties(all, { state: "NY" }).map((l) => l.name)).toEqual(["Kingston Commons", "Bareburger"]);
    expect(filterProperties(all, { attention: "High" })).toEqual([cypress]);
    expect(filterProperties(all, { attention: "Clear" })).toEqual([kingston, empty]);
  });
  it("matches every word against name, address, city and state, ignoring case and accents", () => {
    expect(filterProperties(all, { q: "norwalk" })).toEqual([norwalk]);
    expect(filterProperties(all, { q: "westport 444" })).toEqual([norwalk]);
    expect(filterProperties(all, { q: "  KISCO  " })).toEqual([empty]);
    expect(filterProperties([loc({ name: "Café Plaza" })], { q: "cafe" })).toHaveLength(1);
    expect(filterProperties(all, { q: "nowhere" })).toEqual([]);
  });
});

describe("sortProperties", () => {
  const owned = [norwalk, cypress, kingston, empty];
  it("defaults to attention, worst first, then name", () => {
    expect(sortProperties(owned).map((l) => l.name)).toEqual([
      "Cypress Lake Center",
      "Norwalk Plaza",
      "Bareburger",
      "Kingston Commons",
    ]);
  });
  it("puts missing values last in both directions", () => {
    expect(sortProperties(owned, "population", "desc").map((l) => l.name)).toEqual([
      "Norwalk Plaza",
      "Cypress Lake Center",
      "Bareburger",
      "Kingston Commons",
    ]);
    const asc = sortProperties(owned, "population", "asc").map((l) => l.name);
    expect(asc.slice(0, 2)).toEqual(["Cypress Lake Center", "Norwalk Plaza"]);
    expect(asc.slice(2).sort()).toEqual(["Bareburger", "Kingston Commons"]);
    expect(sortProperties(owned, "aadt", "asc").map((l) => l.name).slice(0, 2)).toEqual(["Norwalk Plaza", "Kingston Commons"]);
  });
  it("orders flood risk inside → near → none and supermarkets by distance", () => {
    expect(sortProperties(owned, "flood", "asc").map((l) => l.name)).toEqual([
      "Cypress Lake Center",
      "Kingston Commons",
      "Norwalk Plaza",
      "Bareburger",
    ]);
    expect(sortProperties(owned, "supermarket", "asc").map((l) => l.name).slice(0, 2)).toEqual([
      "Cypress Lake Center",
      "Kingston Commons",
    ]);
  });
  it("sorts names and states alphabetically and does not mutate its input", () => {
    const copy = [...owned];
    expect(sortProperties(owned, "name", "asc")[0].name).toBe("Bareburger");
    expect(sortProperties(owned, "name", "desc")[0].name).toBe("Norwalk Plaza");
    expect(sortProperties(owned, "state", "asc").map((l) => l.state)).toEqual(["CT", "FL", "NY", "NY"]);
    expect(owned).toEqual(copy);
  });
  it("treats zero alerts as a value, not as missing", () => {
    expect(sortValue(kingston, "alerts")).toBe(0);
    expect(sortValue(empty, "alerts")).toBeNull();
    expect(sortProperties(owned, "alerts", "desc").map((l) => l.name)).toEqual([
      "Cypress Lake Center",
      "Norwalk Plaza",
      "Kingston Commons",
      "Bareburger",
    ]);
  });
});

describe("attention", () => {
  it("ranks and counts owned properties", () => {
    expect([attentionRank("High"), attentionRank("Watch"), attentionRank("Clear"), attentionRank(undefined)]).toEqual([0, 1, 2, 2]);
    expect(attentionCounts(all)).toEqual({ High: 1, Watch: 1, Clear: 2 });
  });
});
