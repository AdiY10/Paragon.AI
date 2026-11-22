import { describe, expect, it } from "vitest";
import { baseStyle, OSM_ATTRIBUTION } from "../src/components/map/baseStyle";

describe("baseStyle", () => {
  it("has no glyphs, no sprite and no symbol layers (the CSP blocks font and sprite hosts)", () => {
    for (const style of [baseStyle("https://tile.openstreetmap.org/{z}/{x}/{y}.png"), baseStyle(null)]) {
      expect(style).not.toHaveProperty("glyphs");
      expect(style).not.toHaveProperty("sprite");
      expect(style.layers.some((layer) => layer.type === "symbol")).toBe(false);
    }
  });
  it("requests tiles only from the configured tile server, greyed on slate", () => {
    const style = baseStyle("https://tile.openstreetmap.org/{z}/{x}/{y}.png");
    expect(style.sources).toEqual({
      basemap: expect.objectContaining({
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        attribution: OSM_ATTRIBUTION,
      }),
    });
    const raster = style.layers.find((layer) => layer.id === "basemap");
    expect(raster?.type === "raster" && raster.paint?.["raster-saturation"]).toBe(-0.9);
    const background = style.layers[0];
    expect(background.type === "background" && background.paint?.["background-color"]).toBe("#F1F5F9");
  });
  it("draws only the background when tiles are disabled", () => {
    const style = baseStyle(null);
    expect(style.sources).toEqual({});
    expect(style.layers.map((layer) => layer.id)).toEqual(["background"]);
  });
});
