import { describe, expect, it } from "vitest";
import { count, floodHeadline, floodTone, monthLabel, signedPct, signedPts } from "../src/area";

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
