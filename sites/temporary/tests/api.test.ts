import { afterEach, describe, expect, it, vi } from "vitest";
import { allLocations, api, ApiError } from "../src/api";

afterEach(() => vi.unstubAllGlobals());
function browser() {
  vi.stubGlobal("window", { location: { origin: "https://radar.example" } });
  vi.stubGlobal("document", {
    querySelector: () => ({ content: "masked-csrf-test-token" }),
  });
}
describe("private API transport", () => {
  it("keeps address search in a CSRF-protected JSON body", async () => {
    browser();
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ results: [] })));
    vi.stubGlobal("fetch", fetcher);
    await api("/api/locations/search/", "POST", { q: "Private test address" });
    const [path, options] = fetcher.mock.calls[0];
    expect(path).toBe("/api/locations/search/");
    expect(options).toMatchObject({
      credentials: "same-origin",
      cache: "no-store",
      body: JSON.stringify({ q: "Private test address" }),
      headers: { "X-CSRFToken": "masked-csrf-test-token" },
    });
  });
  it("rejects cross-origin pagination without requesting the remote page", async () => {
    browser();
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [],
          next: "https://remote.example/api/locations/",
        }),
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    await expect(allLocations()).rejects.toThrow("Invalid pagination origin");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not expose server error content to the interface", async () => {
    browser();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("private internal stack", { status: 409 }),
        ),
    );
    await expect(api("/api/locations/test/", "PATCH", {})).rejects.toEqual(
      new ApiError(409, "This record changed. Reload it before saving."),
    );
  });
  it("loads all portfolio pages before calculating counts", async () => {
    browser();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            results: [{ id: "first" }],
            next: "https://radar.example/api/locations/?page=2",
          }),
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ results: [{ id: "second" }], next: null }),
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    expect(await allLocations()).toEqual([{ id: "first" }, { id: "second" }]);
    expect(fetcher.mock.calls[1][0]).toBe("/api/locations/?page=2");
  });
});
