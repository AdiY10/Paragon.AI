import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { Stat } from "../../../components/ui/Stat";
import { monthLabel, signedPct, signedPts, type Industry } from "../../../lib/format/area";
import { reasonText } from "../../../lib/format/demographics";
import { formatInt, formatUsd } from "../../../lib/format/numbers";

import { SectionShell } from "../SectionShell";

function yoy(i: Industry | undefined) {
  if (!i || i.value === null) return null;
  return i.yoy_pct != null ? `${signedPct(i.yoy_pct)} vs a year earlier` : `Change vs a year earlier: ${reasonText(i.yoy_reason).toLowerCase()}`;
}

/** County economy: jobs, retail jobs and wages, unemployment, housing permits. */
export function MarketSection({ bundle }: { bundle: AnalysisBundle }) {
  const section = bundle.sections.economy;
  const d = section.data;
  return (
    <SectionShell
      id="market"
      title="Market"
      run={sectionRunState(section)}
      reason={section.reason}
      stale={section.stale}
      computedAt={section.computed_at}
      sources={section.sources}
      intro={d ? <p>{d.county.name}. County-level figures describe the local economy, not this property.</p> : undefined}
    >
      {d && (
        <ul className="stat-grid-v2" aria-label="County economy">
          <li>
            <Stat
              label="Private-sector jobs"
              value={formatInt(d.employment.private?.value)}
              sub={yoy(d.employment.private) ?? reasonText(d.employment.private?.reason ?? d.employment.reason)}
              footnote={d.employment.period}
            />
          </li>
          <li>
            <Stat
              label="Retail jobs"
              value={formatInt(d.employment.retail?.value)}
              sub={yoy(d.employment.retail) ?? reasonText(d.employment.retail?.reason ?? d.employment.reason)}
              footnote={
                d.employment.retail?.avg_weekly_wage ? `Average weekly wage ${formatUsd(d.employment.retail.avg_weekly_wage)}` : undefined
              }
            />
          </li>
          <li>
            <Stat
              label="Unemployment rate"
              value={d.unemployment.rate != null ? `${(d.unemployment.rate * 100).toFixed(1)}%` : null}
              sub={d.unemployment.rate != null ? `${signedPts(d.unemployment.change_pts)} vs a year earlier` : reasonText(d.unemployment.reason)}
              footnote={
                d.unemployment.period
                  ? `${monthLabel(d.unemployment.period)}${d.unemployment.preliminary ? " (preliminary)" : ""} · not seasonally adjusted`
                  : undefined
              }
            />
          </li>
          <li>
            <Stat
              label="New homes permitted"
              value={formatInt(d.permits.value)}
              sub={
                d.permits.value != null
                  ? `${signedPct(d.permits.change_pct)} vs prior 12 months${d.permits.prior != null ? ` (${formatInt(d.permits.prior)})` : ""}`
                  : reasonText(d.permits.reason)
              }
              footnote={monthLabel(d.permits.period)}
            />
          </li>
        </ul>
      )}
    </SectionShell>
  );
}
