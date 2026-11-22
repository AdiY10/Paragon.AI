import { describe, expect, it } from "vitest";
import { isActive, legacyRedirect, matchRoute, parseHash } from "../src/app/router";

const ID = "0b9f6c4e-6d1a-4c55-9b0e-2f5c7c1d9a10";

describe("parseHash", () => {
  it("splits path and query", () => {
    const { path, query } = parseHash("#/p/abc?section=risk&x=1");
    expect(path).toBe("/p/abc");
    expect(query.get("section")).toBe("risk");
    expect(query.get("x")).toBe("1");
  });
  it("defaults to the home route and trims trailing slashes", () => {
    expect(parseHash("").path).toBe("/");
    expect(parseHash("#").path).toBe("/");
    expect(parseHash("#/alerts/").path).toBe("/alerts");
    expect(parseHash("#?state=CT").query.get("state")).toBe("CT");
  });
});

describe("matchRoute", () => {
  it("matches the top-level pages", () => {
    expect(matchRoute("/")).toEqual({ name: "properties" });
    expect(matchRoute("/analyze")).toEqual({ name: "analyze" });
    expect(matchRoute("/alerts")).toEqual({ name: "alerts" });
    expect(matchRoute("/compare")).toEqual({ name: "compare" });
    expect(matchRoute("/sources")).toEqual({ name: "sources" });
    expect(matchRoute("/admin")).toEqual({ name: "admin" });
  });
  it("matches property and place analyses by UUID", () => {
    expect(matchRoute("/p/" + ID)).toEqual({ name: "property", id: ID });
    expect(matchRoute("/analyze/" + ID.toUpperCase())).toEqual({ name: "place", id: ID });
  });
  it("rejects ids that are not UUIDs and unknown paths", () => {
    expect(matchRoute("/p/123").name).toBe("notFound");
    expect(matchRoute("/p/" + ID + "/extra").name).toBe("notFound");
    expect(matchRoute("/analyze/../admin").name).toBe("notFound");
    expect(matchRoute("/nope")).toEqual({ name: "notFound", path: "/nope" });
  });
});

describe("legacyRedirect", () => {
  it("maps old routes to new ones, keeping filters", () => {
    expect(legacyRedirect("#/portfolio")).toBe("#/");
    expect(legacyRedirect("#/portfolio?state=CT&attention=High")).toBe("#/?state=CT&attention=High");
    expect(legacyRedirect("#/locations/" + ID)).toBe("#/p/" + ID);
    expect(legacyRedirect("#/screen")).toBe("#/analyze");
    expect(legacyRedirect("#/setup")).toBe("#/");
  });
  it("leaves current routes alone", () => {
    for (const hash of ["", "#/", "#/p/" + ID, "#/analyze", "#/alerts", "#/compare?ids=a,b"])
      expect(legacyRedirect(hash)).toBeNull();
  });
});

describe("isActive", () => {
  it("keeps Properties active on property analyses", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/", "/p/" + ID)).toBe(true);
    expect(isActive("/", "/analyze")).toBe(false);
    expect(isActive("/analyze", "/analyze/" + ID)).toBe(true);
    expect(isActive("/alerts", "/alerts")).toBe(true);
    expect(isActive("/alerts", "/compare")).toBe(false);
  });
});
