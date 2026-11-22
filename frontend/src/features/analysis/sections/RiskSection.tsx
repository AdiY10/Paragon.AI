import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { Badge } from "../../../components/ui/Badge";
import { floodHeadline, sfhaDistance } from "../../../lib/format/area";
import { reasonText } from "../../../lib/format/demographics";
import { SectionShell } from "../SectionShell";

/** FEMA flood zone at and near the pin, and the National Risk Index for the census tract. */
export function RiskSection({ bundle }: { bundle: AnalysisBundle }) {
  const section = bundle.sections.hazards;
  const d = section.data;
  const flood = d?.flood_at_pin;
  const inside = flood ? (flood.in_sfha ?? flood.sfha) && !flood.reason : false;
  const nearby = d ? sfhaDistance(d.flood_nearby) : null;
  return (
    <SectionShell
      id="risk"
      title="Risk"
      run={sectionRunState(section)}
      reason={section.reason}
      stale={section.stale}
      computedAt={section.computed_at}
      sources={section.sources}
    >
      {d && flood && (
        <>
          <div className="risk-grid">
            <div className={inside ? "risk-card flagged" : "risk-card"}>
              <h3>Flood zone at the pin</h3>
              <p className="big-fact">{floodHeadline(flood)}</p>
              <dl className="mini-facts">
                {flood.bfe_ft != null && (
                  <>
                    <dt>Base flood elevation</dt>
                    <dd>{flood.bfe_ft} ft</dd>
                  </>
                )}
                <dt>Nearest high-risk zone</dt>
                <dd>{inside ? "Pin is inside" : (nearby ?? "None within about 150 m")}</dd>
                {flood.dfirm_id && (
                  <>
                    <dt>FEMA map panel</dt>
                    <dd>{flood.dfirm_id}</dd>
                  </>
                )}
              </dl>
            </div>
            <div className="risk-card">
              <h3>National Risk Index (census tract)</h3>
              <p className="big-fact">{d.nri.rating ?? reasonText(d.nri.reason)}</p>
              {d.nri.percentile != null && <p className="fine-print">{d.nri.percentile}th percentile nationally</p>}
              {d.nri.top_hazards && d.nri.top_hazards.length > 0 && (
                <>
                  <h4>Highest-rated hazards</h4>
                  <ul className="hazard-list">
                    {d.nri.top_hazards.map((h) => (
                      <li key={h.hazard}>
                        <span>{h.hazard}</span>
                        <Badge>{h.rating}</Badge>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
          {d.disclaimer && <p className="fine-print">{d.disclaimer}</p>}
        </>
      )}
    </SectionShell>
  );
}
