import { isBusy } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { AnalysisMap, type MapPlace } from "../../../components/map/lazy";
import { AttentionBadge } from "../../../components/ui/Badge";
import { placeName } from "../../../lib/format/area";
import { sourceName } from "../../../lib/format/sources";
import type { Location } from "../../../types";
import { AnalysisProgress } from "../AnalysisProgress";
import { KpiGrid } from "../KpiCard";
import { SectionShell } from "../SectionShell";
import { TakeawayList } from "../TakeawayList";

/** Progress (while busy), key takeaways, key numbers, the map, active alerts and team notes. */
export function OverviewSection({
  bundle,
  record,
  mode,
  gaveUp,
  onCheckAgain,
}: {
  bundle: AnalysisBundle;
  record: Location;
  mode: "property" | "place";
  gaveUp: boolean;
  onCheckAgain: () => void;
}) {
  const pin = record.current_revision;
  const busy = isBusy(bundle.analysis.state);
  const anchors: MapPlace[] = (bundle.sections.businesses.data?.anchors ?? [])
    .filter((a) => a.lat !== undefined && a.lon !== undefined)
    .map((a) => ({ id: a.id, name: placeName(a), group: a.group, lat: a.lat!, lon: a.lon!, distance_mi: a.distance_mi, anchor: true }));
  const rings = record.ring_preset.split("/").map(Number).filter((m) => m > 0);
  const alerts = bundle.signals.filter((s) => s.severity === "High" || s.severity === "Watch");
  return (
    <SectionShell id="overview" title="Overview" run="ready">
      {bundle.analysis.state === "unplaced" && (
        <p className="section-unavailable">This location needs a map pin before it can be analyzed.</p>
      )}
      {busy && <AnalysisProgress bundle={bundle} gaveUp={gaveUp} onCheckAgain={onCheckAgain} />}
      {bundle.risk_badges.length > 0 && (
        <ul className="risk-badges" aria-label="Risk">
          {bundle.risk_badges.map((b) => (
            <li key={b.kind + b.label}>
              {b.label}
              <small> · {sourceName(b.source)}</small>
            </li>
          ))}
        </ul>
      )}
      <TakeawayList takeaways={bundle.takeaways} />
      <KpiGrid kpis={bundle.kpis} mode={mode} />
      {pin.lat !== null && pin.lon !== null && (
        <AnalysisMap
          key={`${pin.lat},${pin.lon}`}
          center={[pin.lon, pin.lat]}
          ringMiles={rings}
          anchors={anchors}
          label="Map of the location, its radius rings and nearby anchors"
          subjectLabel={`${record.name} pin`}
          textAlternativeId="retail-list"
          lazy={false}
        />
      )}
      {mode === "property" && (
        <div className="subsection">
          <h3>Active alerts</h3>
          {alerts.length ? (
            <ul className="alert-list-v2">
              {alerts.map((a) => (
                <li key={a.id}>
                  <AttentionBadge level={a.severity === "High" ? "High" : "Watch"} />
                  <div>
                    <strong>{a.title}</strong>
                    <p>{a.why}</p>
                    {a.next_step && <p className="next-step">Next step: {a.next_step}</p>}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="fine-print">No High or Watch alerts for this property.</p>
          )}
          {alerts.length > 0 && <a href={`#/alerts?property=${record.id}`}>Review these alerts</a>}
        </div>
      )}
      {record.notes && (
        <div className="subsection notes">
          <h3>Team notes</h3>
          <p>{record.notes}</p>
          <span className="fine-print">Written by the Paragon team · details in Record & history</span>
        </div>
      )}
    </SectionShell>
  );
}
