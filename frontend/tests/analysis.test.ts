import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deriveState,
  isBusy,
  newlyReady,
  POLL_GIVE_UP_MS,
  pollDelay,
  readyMessage,
  sectionRunState,
} from "../src/api/analysis";
import { createAnalysis, fetchAnalysis } from "../src/api/hooks";
import type { AnalysisBundle, SectionResult } from "../src/api/types";
import type { Location } from "../src/types";

const ID = "0b9f6c4e-6d1a-4c55-9b0e-2f5c7c1d9a10";
const location = (lat: number | null = 41.1384): Location => ({
  id: ID,
  seed_id: "P03",
  name: "1803 Post Road East",
  address: "1803 Post Road East",
  city: "Westport",
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
  version: 3,
  analysis_version: 2,
  current_revision: {
    id: "r",
    number: 2,
    lat,
    lon: lat === null ? null : -73.3008,
    method: "manual",
    matched_address: "",
    confirmed: true,
    context: {},
    created_at: "",
  },
  created_at: "",
  updated_at: "",
});
const ready = (data: unknown = {}): SectionResult => ({ status: "ready", reason: null, data: data as never, sources: [] });
const pending: SectionResult = { status: "pending", reason: null, data: null, sources: [] };

describe("pollDelay", () => {
  it("polls only while queued, running or partial", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 1500 })).toBe(1500);
    expect(pollDelay({ state: "queued", poll_after_ms: null })).toBe(3000);
    expect(pollDelay({ state: "partial", poll_after_ms: 3000 })).toBe(3000);
    for (const state of ["complete", "failed", "unplaced"] as const) expect(pollDelay({ state, poll_after_ms: 1500 })).toBe(false);
    expect(pollDelay(undefined)).toBe(false);
  });
  it("clamps the server's delay to 1.5–30 s", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 200 })).toBe(1500);
    expect(pollDelay({ state: "running", poll_after_ms: 120_000 })).toBe(30_000);
  });
  it("stops after 15 minutes of polling", () => {
    expect(pollDelay({ state: "running", poll_after_ms: 3000 }, POLL_GIVE_UP_MS - 1)).toBe(3000);
    expect(pollDelay({ state: "running", poll_after_ms: 3000 }, POLL_GIVE_UP_MS)).toBe(false);
    expect(POLL_GIVE_UP_MS).toBe(900_000);
  });
});

describe("section state", () => {
  it("maps section status to what the shell shows", () => {
    expect(sectionRunState(ready())).toBe("ready");
    expect(sectionRunState({ ...ready(), data: null })).toBe("unavailable");
    expect(sectionRunState(pending)).toBe("loading");
    expect(sectionRunState({ ...pending, status: "running" })).toBe("loading");
    expect(sectionRunState({ status: "unavailable", reason: "Needs a map pin", data: null, sources: [] })).toBe("unavailable");
    expect(sectionRunState(undefined)).toBe("loading");
  });
  it("derives the overall state", () => {
    expect(deriveState(false, [ready()])).toBe("unplaced");
    expect(deriveState(true, [ready(), ready()])).toBe("complete");
    expect(deriveState(true, [ready(), pending])).toBe("partial");
    expect(deriveState(true, [pending, pending])).toBe("running");
    expect(deriveState(true, [{ status: "unavailable", reason: "x", data: null, sources: [] }])).toBe("failed");
    expect(isBusy("partial")).toBe(true);
    expect(isBusy("complete")).toBe(false);
  });
  it("announces sections that became ready, then completion", () => {
    const before = { sections: { businesses: pending, traffic: pending } } as unknown as AnalysisBundle;
    const after = { sections: { businesses: ready(), traffic: pending } } as unknown as AnalysisBundle;
    expect(newlyReady(before, after)).toEqual(["businesses"]);
    expect(readyMessage(["businesses"], false)).toBe("Retail landscape is ready.");
    expect(readyMessage(["traffic", "hazards"], false)).toBe("Access & traffic and Risk are ready.");
    expect(readyMessage([], true)).toBe("Analysis complete.");
    expect(readyMessage([], false)).toBe("");
  });
});

describe("API calls", () => {
  beforeEach(() => vi.stubGlobal("document", { querySelector: () => ({ content: "csrf" }) }));
  afterEach(() => vi.unstubAllGlobals());
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  it("reads the whole analysis from one bundle request and fills missing lists", async () => {
    const fetcher = vi.fn().mockResolvedValue(json({ location: location(), analysis: { state: "complete" }, sections: {} }));
    vi.stubGlobal("fetch", fetcher);
    const result = await fetchAnalysis(ID);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/locations/${ID}/analysis/`);
    expect(result).toMatchObject({ kpis: [], takeaways: [], signals: [], risk_badges: [] });
  });
  it("treats an unknown property as a 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "No Location matches the given query." }, 404)));
    await expect(fetchAnalysis(ID)).rejects.toMatchObject({ status: 404 });
  });
  it("returns B5's 503 body (geocoder down) instead of throwing, and passes other errors on", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ location: location(), geocode: { status: "unavailable" }, next: "place_pin" }, 503)),
    );
    await expect(createAnalysis({ address: "1 Main St, Anywhere, CT" })).resolves.toMatchObject({
      geocode: { status: "unavailable" },
      next: "place_pin",
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Choose a point in the United States." }, 400)));
    await expect(createAnalysis({ lat: 10, lon: 10 })).rejects.toMatchObject({ status: 400, detail: "Choose a point in the United States." });
  });
});
