import norwalk from "./fixtures/norwalk.json?raw";
import mountKisco from "./fixtures/mount_kisco.json?raw";
import kingston from "./fixtures/kingston.json?raw";
import { describe, it, expect } from "vitest";
import {
  parseCensus,
  normalizeAddress,
  locationAddress,
} from "../worker/census.js";
const fixture = (name: string) =>
  (({ norwalk, mount_kisco: mountKisco, kingston }) as Record<string, string>)[
    name
  ];
it("assembles address tokens without duplicate cities or missing state abbreviations", () => {
  expect(normalizeAddress("a   b")).toBe("a b");
  expect(
    locationAddress({
      address: "123 Market Street",
      city: "Stuttgart",
      state: "AR",
    }),
  ).toBe("123 Market Street, Stuttgart, AR");
  expect(
    locationAddress({
      address: "444 Westport Avenue, Norwalk, CT",
      city: "Norwalk",
      state: "CT",
    }),
  ).toBe("444 Westport Avenue, Norwalk, CT");
});
describe("Census adapter parity with canonical reference fixtures", () => {
  it("keeps CT current county and decennial blocks separate", () => {
    const result = parseCensus(fixture("norwalk"));
    expect(result.status).toBe("matched");
    expect(result.candidates[0]).toMatchObject({
      method: "census_interpolated",
      match_quality: "not_reported",
      lat: 41.12661107292,
      geographies: {
        county: { geoid: "09190" },
        block: { geoid: "090010435001001", geography_vintage: "Census2020" },
      },
    });
  });
  it("preserves real ambiguity and no match", () => {
    expect(parseCensus(fixture("mount_kisco")).candidates).toHaveLength(2);
    expect(parseCensus(fixture("mount_kisco")).status).toBe("ambiguous");
    expect(parseCensus(fixture("kingston")).status).toBe("no_match");
  });
  it.each([true, "41", 91, null])("rejects invalid coordinate %s", (value) => {
    const data = JSON.parse(fixture("norwalk"));
    data.result.addressMatches[0].coordinates.y = value;
    expect(() => parseCensus(JSON.stringify(data))).toThrow("SCHEMA_ERROR");
  });
});
