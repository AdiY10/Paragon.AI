import { describe, expect, it } from "vitest";
import { ITEM_LABELS, presenceLabel } from "../src/Tenants";

describe("tenant labels", () => {
  it("labels listing claims honestly", () => {
    expect(presenceLabel("listed_unverified")).toBe("From public listing (unverified)");
    expect(presenceLabel("unverified")).toBe("User-provided");
    expect(ITEM_LABELS["1.03"]).toBe("Bankruptcy or receivership");
  });
});
