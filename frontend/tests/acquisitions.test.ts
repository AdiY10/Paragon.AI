import { describe, expect, it } from "vitest";
import { readCompare, toggleCompare } from "../src/Acquisitions";

describe("compare selection", () => {
  it("adds, removes and keeps at most four", () => {
    expect(toggleCompare([], "a")).toEqual(["a"]);
    expect(toggleCompare(["a", "b"], "a")).toEqual(["b"]);
    expect(toggleCompare(["a", "b", "c", "d"], "e")).toEqual(["b", "c", "d", "e"]);
  });
  it("survives unavailable storage", () => {
    expect(readCompare()).toEqual([]);
  });
});
