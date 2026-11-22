import { describe, expect, it } from "vitest";
import {
  cleanIds,
  compareHref,
  LIMIT_MESSAGE,
  MAX_COMPARE,
  parseIds,
  readSelection,
  toggleSelection,
  writeSelection,
} from "../src/features/compare/selection";

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

describe("compare selection", () => {
  it("adds and removes ids", () => {
    expect(toggleSelection([], id(1))).toEqual({ ids: [id(1)], refused: false });
    expect(toggleSelection([id(1), id(2)], id(1))).toEqual({ ids: [id(2)], refused: false });
  });
  it("refuses a fifth instead of dropping one", () => {
    const four = [1, 2, 3, 4].map(id);
    expect(MAX_COMPARE).toBe(4);
    expect(toggleSelection(four, id(5))).toEqual({ ids: four, refused: true });
    expect(toggleSelection(four, id(2)).ids).toEqual([id(1), id(3), id(4)]);
    expect(LIMIT_MESSAGE).toBe("Up to 4. Remove one first.");
  });
  it("accepts only unique UUIDs, at most four, from storage or the URL", () => {
    expect(cleanIds([id(1), id(1).toUpperCase(), "nope", 3, id(2), id(3), id(4), id(5)])).toEqual([1, 2, 3, 4].map(id));
    expect(cleanIds("not a list")).toEqual([]);
    expect(parseIds(`${id(1)},,${id(2)},../admin`)).toEqual([id(1), id(2)]);
    expect(parseIds(null)).toEqual([]);
    expect(compareHref([id(1), id(2)])).toBe(`#/compare?ids=${id(1)},${id(2)}`);
  });
  it("survives unavailable storage (memory fallback)", () => {
    expect(readSelection()).toEqual([]);
    writeSelection([id(7)]);
    expect(readSelection()).toEqual([id(7)]);
    writeSelection([]);
  });
});
