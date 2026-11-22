import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { Takeaway } from "../src/api/types";
import { TakeawayList } from "../src/features/analysis/TakeawayList";
import { sectionStatus, SECTIONS, sectionsFor } from "../src/features/analysis/sections";
import type { AnalysisBundle } from "../src/api/types";

const t = (p: Partial<Takeaway>): Takeaway => ({
  text: "Inside FEMA high-risk flood zone AE (base flood elevation 9 ft)",
  tone: "caution",
  section: "risk",
  source: "SRC-11",
  period: null,
  ...p,
});

describe("TakeawayList", () => {
  it("renders an ordered list with tone word, sentence, source name and a link to the section", () => {
    const html = renderToStaticMarkup(<TakeawayList takeaways={[t({}), t({ tone: "positive", text: "Strong", section: "trade-area", source: "SRC-03", period: "ACS 2020–2024" })]} />);
    expect(html).toContain("<ol");
    expect(html).toContain("Key takeaways");
    expect(html).toContain("Concern");
    expect(html).toContain("Strength");
    expect(html).toContain("FEMA flood maps");
    expect(html).toContain("Census ACS 5-year · ACS 2020–2024");
    expect(html).toContain('href="#risk"');
    expect(html).not.toContain("SRC-11");
  });
  it("shows at most five and nothing at all when empty", () => {
    const html = renderToStaticMarkup(<TakeawayList takeaways={Array.from({ length: 7 }, (_, i) => t({ text: `T${i}` }))} />);
    expect(html.match(/class="takeaway /g)).toHaveLength(5);
    expect(renderToStaticMarkup(<TakeawayList takeaways={[]} />)).toBe("");
  });
  it("links nothing for an overview takeaway", () => {
    expect(renderToStaticMarkup(<TakeawayList takeaways={[t({ section: "overview" })]} />)).not.toContain("See details");
  });
});

describe("section menu", () => {
  it("has ten sections for a property and nine (no tenants) for a new place", () => {
    expect(SECTIONS.map((s) => s.id)).toEqual([
      "overview", "trade-area", "daytime", "retail", "access", "risk", "market", "tenants", "ranking", "sources",
    ]);
    expect(sectionsFor("property")).toHaveLength(10);
    expect(sectionsFor("place").map((s) => s.id)).not.toContain("tenants");
  });
  it("derives each dot from its sections", () => {
    const bundle = {
      analysis: { state: "partial" },
      sections: {
        demographics: { status: "ready", data: {}, reason: null, sources: [] },
        businesses: { status: "pending", data: null, reason: null, sources: [] },
        hazards: { status: "unavailable", data: null, reason: "x", sources: [] },
      },
    } as unknown as AnalysisBundle;
    const status = (id: string) => sectionStatus(SECTIONS.find((s) => s.id === id)!, bundle);
    expect(status("trade-area")).toBe("ready");
    expect(status("retail")).toBe("loading");
    expect(status("risk")).toBe("unavailable");
    expect(status("overview")).toBe("loading");
    expect(status("sources")).toBe("none");
  });
});
