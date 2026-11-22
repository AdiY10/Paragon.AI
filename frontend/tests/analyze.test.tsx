import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { sectionReasonText } from "../src/api/analysis";
import { stateText } from "../src/features/analyze/RecentAnalyses";
import { CandidateList } from "../src/features/analyze/CandidateList";

describe("section reasons", () => {
  it("turns server codes into plain language and keeps sentences as they are", () => {
    expect(sectionReasonText("NOT_PROVIDED")).toBe("Needs a map pin before it can be analyzed.");
    expect(sectionReasonText("SOURCE_ERROR")).toContain("will try again");
    expect(sectionReasonText("TIMEOUT")).toContain("will try again");
    expect(sectionReasonText("NOT_COMPUTED")).toContain("retries automatically");
    expect(sectionReasonText("Place the pin first.")).toBe("Place the pin first.");
    expect(sectionReasonText(null)).toBe("This information is not available for this location.");
    expect(sectionReasonText("WHATEVER")).toBe("This information is not available for this location.");
  });
});

describe("Analyze page pieces", () => {
  it("labels every analysis state", () => {
    expect(stateText("complete")).toBe("Ready");
    expect(stateText("running")).toBe("Analyzing");
    expect(stateText("unplaced")).toBe("Needs a pin");
    expect(stateText("failed")).toBe("Could not finish");
  });
  it("lists ambiguous matches with nothing preselected and the submit disabled", () => {
    const html = renderToStaticMarkup(
      <CandidateList
        candidates={[
          { index: 0, matched_address: "445 MAIN ST, MOUNT KISCO, NY, 10549", lat: 41.2041, lon: -73.7271 },
          { index: 1, matched_address: "445 MAIN ST, MOUNT KISCO, NY, 10549", lat: 41.2052, lon: -73.7265 },
        ]}
        busy={false}
        onChoose={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(html).toContain("Choose the matching address");
    expect(html.match(/type="radio"/g)).toHaveLength(2);
    expect(html).not.toContain("checked");
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Analyze this address/);
  });
});
