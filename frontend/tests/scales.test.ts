import { describe, expect, it } from "vitest";
import { indexSpan, niceMax, pctOf, position } from "../src/lib/scales";

describe("niceMax", () => {
  it("rounds up to 1, 2, 2.5 or 5 times a power of ten", () => {
    expect(niceMax(84000)).toBe(100000);
    expect(niceMax(67312)).toBe(100000);
    expect(niceMax(21000)).toBe(25000);
    expect(niceMax(180)).toBe(200);
    expect(niceMax(0.43)).toBe(0.5);
    expect(niceMax(5)).toBe(5);
    expect(niceMax(1)).toBe(1);
  });
  it("falls back to 1 for empty or non-positive data", () => {
    expect(niceMax(0)).toBe(1);
    expect(niceMax(-3)).toBe(1);
    expect(niceMax(Number.NaN)).toBe(1);
  });
});

describe("pctOf", () => {
  it("is zero-based and clamped", () => {
    expect(pctOf(50, 200)).toBe(25);
    expect(pctOf(300, 200)).toBe(100);
    expect(pctOf(-5, 200)).toBe(0);
    expect(pctOf(5, 0)).toBe(0);
  });
});

describe("position", () => {
  it("maps a value onto a track and clamps it", () => {
    expect(position(75, [50, 150])).toBe(25);
    expect(position(10, [0, 100])).toBe(10);
    expect(position(500, [0, 100])).toBe(100);
  });
});

describe("indexSpan", () => {
  it("diverges from 100 at the centre of a 50–150 track", () => {
    expect(indexSpan(125)).toEqual({ left: 50, width: 25, center: 50, direction: "above", overflow: null });
    expect(indexSpan(80)).toEqual({ left: 30, width: 20, center: 50, direction: "below", overflow: null });
    expect(indexSpan(100)).toEqual({ left: 50, width: 0, center: 50, direction: "equal", overflow: null });
  });
  it("clamps beyond the track and flags the overflow", () => {
    expect(indexSpan(212)).toMatchObject({ left: 50, width: 50, overflow: "high" });
    expect(indexSpan(31)).toMatchObject({ left: 0, width: 50, overflow: "low" });
  });
});
