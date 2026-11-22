import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { formatChangePct, formatInt } from "../../../lib/format/numbers";
import { SectionShell } from "../SectionShell";

/** Road counts near the pin: vehicles on the road (AADT), never visits. */
export function AccessSection({ bundle }: { bundle: AnalysisBundle }) {
  const section = bundle.sections.traffic;
  const d = section.data;
  return (
    <SectionShell
      id="access"
      title="Access & traffic"
      run={sectionRunState(section)}
      reason={section.reason}
      stale={section.stale}
      computedAt={section.computed_at}
      sources={section.sources}
      intro={<p>Average vehicles per day on nearby roads (state counts reported to FHWA). Traffic is not shopper visits.</p>}
    >
      {d &&
        (d.roads.length ? (
          <ul className="road-cards">
            {d.roads.map((r, index) => (
              <li key={`${r.label}-${index}`} className="road-card">
                <p className="road-name">{r.label}</p>
                <p className="road-value">
                  {formatInt(r.aadt)} <span className="unit">vehicles/day</span>
                </p>
                <p className="road-meta">
                  {[
                    `${r.year} estimate${r.count_year && r.count_year !== r.year ? `, counted ${r.count_year}` : ""}`,
                    r.distance_m != null ? `about ${r.distance_m} m from the pin` : null,
                    r.road_class,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <p className="road-change">
                  {r.change_pct !== null && r.prior_year
                    ? `${formatChangePct(r.change_pct)} vs ${r.prior_year}${r.prior_aadt ? ` (${formatInt(r.prior_aadt)})` : ""}`
                    : r.reason === "SAME_COUNT"
                      ? "Estimate carried forward; no new count"
                      : "No earlier count to compare"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="fine-print">No counted road within {d.radius_m} m of the pin.</p>
        ))}
      {d?.note && <p className="fine-print">{d.note}</p>}
    </SectionShell>
  );
}
