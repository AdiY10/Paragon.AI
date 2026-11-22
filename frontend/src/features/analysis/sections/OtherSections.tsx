import type { AnalysisBundle, SourceRef } from "../../../api/types";
import { PercentileBullet } from "../../../components/charts";
import { dateLabel } from "../../../lib/format/dates";
import { sourceName } from "../../../lib/format/sources";
import TenantsPanel from "../../../Tenants";
import type { Location } from "../../../types";
import { kpiValue } from "../KpiCard";
import { SectionShell } from "../SectionShell";

/** Tenants & SEC watch (owned properties only). */
export function TenantsSection({ location, isAdmin }: { location: Location; isAdmin: boolean }) {
  return (
    <SectionShell id="tenants" title="Tenants & SEC watch" run="ready">
      <TenantsPanel location={location} isAdmin={isAdmin} />
    </SectionShell>
  );
}

/** Where the property sits among the owned portfolio on each ranked figure. */
export function RankingSection({ bundle, mode }: { bundle: AnalysisBundle; mode: "property" | "place" }) {
  const ranked = bundle.kpis.filter((k) => k.ranked !== false);
  const any = ranked.some((k) => k.percentile != null);
  const busy = bundle.analysis.state === "queued" || bundle.analysis.state === "running";
  const portfolio = bundle.portfolio;
  return (
    <SectionShell
      id="ranking"
      title="Ranking vs portfolio"
      run={busy && !any ? "loading" : any ? "ready" : "unavailable"}
      reason={
        portfolio && !portfolio.ready
          ? `Rankings need at least ${portfolio.min} owned properties with data.`
          : "Rankings appear once this location's figures are in."
      }
      intro={
        <p>
          {mode === "place" ? "Where this place would sit" : "Where this property sits"} among Paragon's owned properties,
          lowest to highest. Higher is not always better; each figure describes the surrounding area.
        </p>
      }
    >
      <div className="bullet-list">
        {ranked.map((k) =>
          k.rank != null && k.of != null ? (
            <PercentileBullet
              key={k.key}
              label={k.label}
              value={kpiValue(k)}
              percentile={k.percentile ?? null}
              rank={k.rank}
              of={k.of}
              mode={mode}
            />
          ) : (
            <LegacyBullet key={k.key} label={k.label} value={kpiValue(k)} percentile={k.percentile ?? null} of={k.of ?? null} mode={mode} />
          ),
        )}
      </div>
    </SectionShell>
  );
}

/** Percentile without a rank (older servers): "Above 91% of 34 owned properties". */
function LegacyBullet({
  label,
  value,
  percentile,
  of,
  mode,
}: {
  label: string;
  value: string | null;
  percentile: number | null;
  of: number | null;
  mode: "property" | "place";
}) {
  if (percentile === null || of === null)
    return <PercentileBullet label={label} value={value} percentile={null} rank={null} of={null} reason="Not ranked: this figure is not available here" />;
  return (
    <div className="bullet">
      <div className="bullet-head">
        <span className="bar-label">{label}</span>
        {value && <span className="bullet-value">{value}</span>}
      </div>
      <span className="bullet-track" aria-hidden="true">
        <span className="bullet-fill" style={{ width: `${percentile}%` }} />
        <span className="bullet-median" style={{ left: "50%" }} />
        <span className="bullet-marker" style={{ left: `${percentile}%` }} />
      </span>
      <span className="bullet-scale" aria-hidden="true">
        <span>Lowest</span>
        <span>Median</span>
        <span>Highest</span>
      </span>
      <p className="bullet-text">
        {mode === "place" ? "Would be above" : "Above"} {percentile}% of {of} other owned properties
      </p>
    </div>
  );
}

/** Every source with period and checked date, plus method notes; collapsed by default. */
export function SourcesSection({ bundle }: { bundle: AnalysisBundle }) {
  const all: SourceRef[] = bundle.sources.length
    ? bundle.sources
    : Object.values(bundle.sections).flatMap((s) => s.sources ?? []);
  const caveats = bundle.sections.demographics.data?.caveats ?? [];
  return (
    <SectionShell id="sources" title="Sources & methods" run="ready">
      <details className="sources-details">
        <summary>Show sources and methods</summary>
        {all.length ? (
          <ul className="source-list-v2">
            {all.map((s, index) => (
              <li key={`${s.id}-${s.period}-${index}`}>
                <strong>{s.name || sourceName(s.id)}</strong>
                <small>
                  {[s.period, s.checked_at || s.retrieved_at ? `checked ${dateLabel(s.checked_at || s.retrieved_at)}` : null, s.stale ? "out of date" : null]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
                {s.url && (
                  <a href={s.url} target="_blank" rel="noreferrer">
                    Source documentation
                  </a>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="fine-print">Sources appear as each section's data arrives.</p>
        )}
        <h3>Method notes</h3>
        <ul className="method-notes">
          {caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
          <li>Radius rings are straight-line circles around the pin, not a measured trade area.</li>
          <li>Traffic counts are vehicles on the road, not visits to the property.</li>
          <li>Business listings come from Overture Maps; a closure is a possibility to verify, not a fact.</li>
          <li>Summaries are written from the numbers with fixed rules; nothing on this page is generated by AI.</li>
        </ul>
      </details>
    </SectionShell>
  );
}
