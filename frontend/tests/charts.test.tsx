import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BarList, Dumbbell, GroupedBarList, IndexBar, PercentileBullet, Sparkline } from "../src/components/charts";
import { AttentionBadge } from "../src/components/ui/Badge";
import { Missing, Stat } from "../src/components/ui/Stat";

const html = (node: React.ReactElement) => renderToStaticMarkup(node);
const widths = (markup: string) => [...markup.matchAll(/width:\s*([\d.]+)%/g)].map((m) => Number(m[1]));

describe("BarList", () => {
  it("prints every value and draws zero-based bars on a shared scale", () => {
    const markup = html(
      <BarList
        label="Jobs by sector"
        max={1000}
        items={[
          { key: "retail", label: "Retail", value: 500, display: "500" },
          { key: "food", label: "Food service", value: 250, display: "250" },
        ]}
      />,
    );
    expect(markup).toContain('aria-label="Jobs by sector"');
    expect(markup).toContain(">500<");
    expect(markup).toContain(">250<");
    expect(widths(markup)).toEqual([50, 25]);
    expect(markup).toContain('aria-hidden="true"');
  });
  it("shows the reason and no bar for a missing value", () => {
    const markup = html(
      <BarList label="x" items={[{ key: "a", label: "Office", value: null, reason: "Not published by Census" }]} />,
    );
    expect(markup).toContain("Not published by Census");
    expect(markup).not.toContain("bar-fill");
    expect(markup).not.toMatch(/>0</);
  });
});

describe("GroupedBarList", () => {
  it("names the series in a legend, marks the portfolio median and prints it", () => {
    const markup = html(
      <GroupedBarList
        label="Grocery stores"
        series={["Within 1 mi", "Within 3 mi"]}
        max={10}
        rows={[{ key: "grocery", label: "Grocery", values: [{ value: 2 }, { value: 6 }], median: 4, medianDisplay: "4" }]}
      />,
    );
    expect(markup).toContain("Within 1 mi");
    expect(markup).toContain("Within 3 mi");
    expect(markup).toContain("Portfolio median");
    expect(markup).toContain("bar-median");
    expect(markup.replace(/<!-- -->/g, "")).toContain("Portfolio median: 4");
    expect(widths(markup)).toEqual([20, 60]);
  });
});

describe("Dumbbell", () => {
  it("prints before, after and the change on one zero-based scale", () => {
    const markup = html(
      <Dumbbell
        label="Population change"
        periods={["2015–2019", "2020–2024"]}
        max={100000}
        rows={[
          {
            key: "pop",
            label: "Population",
            before: 65000,
            after: 67312,
            beforeDisplay: "65,000",
            afterDisplay: "67,312",
            change: "+3.6%",
            note: "Significant",
            tone: "good",
          },
        ]}
      />,
    );
    expect(markup).toContain("65,000");
    expect(markup).toContain("67,312");
    expect(markup).toContain("+3.6%");
    expect(markup).toContain("change-good");
    expect(markup).toContain("2015–2019");
    expect(markup).toContain("left:65%");
  });
  it("prints the reason when either end is missing", () => {
    const markup = html(
      <Dumbbell
        label="x"
        periods={["a", "b"]}
        rows={[{ key: "k", label: "Income", before: null, after: 5, reason: "Unavailable: census geography changed" }]}
      />,
    );
    expect(markup).toContain("census geography changed");
    expect(markup).not.toContain("dumbbell-dot");
  });
});

describe("PercentileBullet", () => {
  it("places the marker by percentile and prints the rank sentence", () => {
    const markup = html(<PercentileBullet label="People within 3 mi" value="67,312" percentile={91} rank={4} of={35} />);
    expect(markup).toContain("Ranks 4 of 35 owned properties");
    expect(markup).toContain("left:91%");
    expect(markup).toContain("left:50%");
  });
  it("uses 'Would rank' for a new place and explains when there is no rank", () => {
    expect(html(<PercentileBullet label="x" percentile={10} rank={30} of={35} mode="place" />)).toContain(
      "Would rank 30 of 35 owned properties",
    );
    expect(html(<PercentileBullet label="x" percentile={null} rank={null} of={null} />)).toContain("Not ranked");
  });
});

describe("IndexBar", () => {
  it("diverges from 100 and keeps the exact index in text when clamped", () => {
    const markup = html(<IndexBar label="Median household income" index={212} />);
    expect(markup).toContain("212 · 112% above the US average");
    expect(markup).toContain("overflow-high");
    expect(markup).toContain("left:50%;width:50%");
  });
  it("shows a reason for a missing index", () => {
    expect(html(<IndexBar label="Rent" index={null} reason="Not published by Census" />)).toContain(
      "Not published by Census",
    );
  });
});

describe("Sparkline", () => {
  it("renders only when a real series exists", () => {
    expect(html(<Sparkline label="Traffic" values={[10]} />)).toBe("");
    expect(html(<Sparkline label="Traffic" values={[10, null]} />)).toBe("");
    const markup = html(<Sparkline label="Traffic 2023 to 2025" values={[10, 12, 11]} />);
    expect(markup).toContain('role="img"');
    expect(markup).toContain('aria-label="Traffic 2023 to 2025"');
    expect(markup).toContain("<circle");
  });
});

describe("UI kit", () => {
  it("shows attention as icon + word", () => {
    expect(html(<AttentionBadge level="High" />)).toContain("High");
    expect(html(<AttentionBadge level={undefined} />)).toContain("Clear");
  });
  it("prints a dash with hidden 'Unavailable' for a missing stat", () => {
    const markup = html(<Stat label="People within 3 mi" value={null} />);
    expect(markup).toContain("—");
    expect(markup).toContain('class="sr-only">Unavailable');
    expect(html(<Missing reason="Needs a pin" />)).toContain("Needs a pin");
  });
});
