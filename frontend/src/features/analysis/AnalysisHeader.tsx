import { useState } from "react";
import { ChevronRight, Layers3, Star } from "lucide-react";
import { useKeepAnalysis } from "../../api/hooks";
import type { AnalysisBundle } from "../../api/types";
import { AttentionBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { LiveRegion } from "../../components/ui/LiveRegion";
import { dateLabel } from "../../lib/format/dates";
import type { Location } from "../../types";
import { LIMIT_MESSAGE, useCompareSelection } from "../compare/selection";
import { PropertyActionsMenu } from "./admin/PropertyActionsMenu";

function dataAsOf(bundle: AnalysisBundle | undefined) {
  if (!bundle) return null;
  const dates = Object.values(bundle.sections)
    .map((s) => s.computed_at)
    .filter((d): d is string => !!d)
    .sort();
  return dates.length ? dates[dates.length - 1] : null;
}

/** Name, address, attention, "Data as of …", and the per-mode actions. */
export function AnalysisHeader({
  record,
  bundle,
  mode,
  isAdmin,
}: {
  record: Location;
  bundle: AnalysisBundle | undefined;
  mode: "property" | "place";
  isAdmin: boolean;
}) {
  const compare = useCompareSelection();
  const keep = useKeepAnalysis();
  const [message, setMessage] = useState("");
  const inCompare = compare.ids.includes(record.id);
  const asOf = dataAsOf(bundle);
  const kept = bundle?.location.kept ?? false;
  const place = [record.city, record.state].filter(Boolean).join(", ");
  return (
    <header className="analysis-header">
      <nav aria-label="Breadcrumb" className="breadcrumb-v2">
        <a href={mode === "property" ? "#/" : "#/analyze"}>{mode === "property" ? "Properties" : "Analyze"}</a>
        <ChevronRight size={14} aria-hidden="true" />
        <span aria-current="page">{mode === "property" ? "Property analysis" : "New place"}</span>
      </nav>
      <div className="analysis-title-row">
        <div className="analysis-title">
          <h1>{record.name}</h1>
          <p className="analysis-address">
            {bundle?.location.display_label ||
              (record.city && record.address.includes(record.city) ? record.address : [record.address, place].filter(Boolean).join(", "))}
          </p>
          <p className="analysis-meta">
            {mode === "property" && <AttentionBadge level={record.attention} />}
            {mode === "place" && <span className="place-note">New place · not monitored · removed after 90 days unless starred</span>}
            {asOf && <span>Data as of {dateLabel(asOf)}</span>}
          </p>
        </div>
        <div className="analysis-actions">
          {mode === "place" && (
            <Button
              variant="secondary"
              size="sm"
              aria-pressed={kept}
              disabled={keep.isPending}
              onClick={() =>
                keep.mutate(
                  { id: record.id, kept: !kept },
                  {
                    onSuccess: (r) => setMessage(r.kept ? "Starred: this analysis is kept." : "Star removed."),
                    onError: (e) => setMessage(e instanceof Error ? e.message : "Could not change the star."),
                  },
                )
              }
            >
              <Star size={14} aria-hidden="true" fill={kept ? "currentColor" : "none"} />
              {kept ? "Starred" : "Star"}
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            aria-pressed={inCompare}
            onClick={() => {
              if (!compare.toggle(record.id)) setMessage(LIMIT_MESSAGE);
              else setMessage(inCompare ? "Removed from compare." : "Added to compare.");
            }}
          >
            <Layers3 size={14} aria-hidden="true" />
            Compare
          </Button>
          {compare.ids.length >= 2 && (
            <a className="btn btn-ghost btn-sm" href={"#/compare?ids=" + compare.ids.join(",")}>
              Open compare ({compare.ids.length})
            </a>
          )}
          {mode === "property" && isAdmin && <PropertyActionsMenu location={record} />}
        </div>
      </div>
      {keep.error && (
        <p className="section-unavailable" role="alert">
          {keep.error instanceof Error ? keep.error.message : "Could not change the star."}
        </p>
      )}
      <LiveRegion message={message} />
    </header>
  );
}
