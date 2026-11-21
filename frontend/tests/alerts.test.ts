import { describe, expect, it } from "vitest";
import { evidenceRows } from "../src/alertText";

describe("evidenceRows", () => {
  it("explains unemployment in plain English", () => {
    const rows = evidenceRows("SIG-05", { rate: 0.05, prior_rate: 0.038, change_pts: 1.2, more_than_state_pts: 0.6, z: 3 });
    expect(rows).toEqual([
      ["Unemployment rate (latest month)", "5.0%"],
      ["A year earlier", "3.8%"],
      ["Rise vs a year earlier", "+1.2 points"],
      ["Rose more than the state by", "+0.6 points"],
    ]);
  });
  it("hides missing values and internal fields", () => {
    const rows = evidenceRows("SIG-11", { zone: "AE", distance_m: 40, dfirm_id: "x", source_link: "https://x" });
    expect(rows).toEqual([
      ["FEMA flood zone", "AE"],
      ["Distance to the high-risk zone", "about 40 m from the pin"],
    ]);
  });
});
