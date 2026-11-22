import { AlertCircle, ArrowUpRight, CircleCheck, Clock } from "lucide-react";
import { useSources } from "../api/hooks";
import { Badge } from "../components/ui/Badge";
import { Drawer } from "../components/ui/Drawer";
import { ErrorState } from "../components/ui/ErrorState";
import { Skeleton } from "../components/ui/Skeleton";
import { dateLabel } from "../lib/format/dates";
import type { Source } from "../types";

function StatusBadge({ status }: { status: string }) {
  if (status === "OK")
    return (
      <Badge tone="accent" icon={<CircleCheck size={12} aria-hidden="true" />}>
        Up to date
      </Badge>
    );
  if (status === "Failing")
    return (
      <Badge icon={<AlertCircle size={12} aria-hidden="true" />}>
        Could not refresh
      </Badge>
    );
  return <Badge icon={<Clock size={12} aria-hidden="true" />}>{status}</Badge>;
}

function lastSuccess(source: Source) {
  const dates = source.health_scopes.map((s) => s.last_success_at).filter((d): d is string => !!d).sort();
  return dates.length ? dates[dates.length - 1] : null;
}

/** `#/sources`: every public source, what it covers, when it was last checked, and its licence. */
export function SourcesPage() {
  const sources = useSources();
  return (
    <div className="sources-page">
      <header className="page-header">
        <h1>Data sources</h1>
        <p className="page-lead">
          Every figure in Paragon Radar comes from one of these public sources. Each shows its coverage, when it was last
          checked and its licence. Nothing is estimated or generated.
        </p>
      </header>
      <p className="fine-print">
        Map privacy: OpenStreetMap receives your IP address and the map area you view. Property names, notes and account
        details stay in this workspace.
      </p>
      {sources.error ? (
        <ErrorState error={sources.error} title="Sources could not load." onRetry={() => void sources.refetch()} />
      ) : !sources.data ? (
        <Skeleton lines={6} height={64} />
      ) : (
        <ul className="source-cards" aria-label="Sources">
          {sources.data.map((source) => {
            const checked = lastSuccess(source);
            return (
              <li key={source.id} className="source-card-v2">
                <div className="source-card-head">
                  <span className="source-provider">{source.provider}</span>
                  <StatusBadge status={source.status} />
                </div>
                <h2>{source.name}</h2>
                <p>{source.purpose}</p>
                <p className="fine-print">
                  {source.coverage}
                  {checked ? ` · last good check ${dateLabel(checked)}` : " · no completed check yet"}
                </p>
                <Drawer
                  title={source.name}
                  description={source.provider}
                  trigger={
                    <button type="button" className="text-link-button">
                      Source details<span className="sr-only">: {source.name}</span>
                    </button>
                  }
                >
                  <dl className="facts">
                    <dt>Coverage</dt>
                    <dd>{source.coverage}</dd>
                    <dt>Refresh</dt>
                    <dd>{source.cadence}</dd>
                    <dt>Licence</dt>
                    <dd>{source.licence}</dd>
                    <dt>Attribution</dt>
                    <dd>{source.attribution}</dd>
                    <dt>Privacy</dt>
                    <dd>{source.privacy_note}</dd>
                  </dl>
                  <a href={source.documentation_url} target="_blank" rel="noreferrer">
                    Provider documentation <ArrowUpRight size={14} aria-hidden="true" />
                  </a>
                  <h3>Recorded checks</h3>
                  {source.health_scopes.length ? (
                    <ul className="scope-list">
                      {source.health_scopes.map((scope) => (
                        <li key={scope.scope}>
                          <StatusBadge status={scope.status} />
                          <span>
                            {scope.data_period ?? "No published data period"}
                            <small>Last successful check: {dateLabel(scope.last_success_at)}</small>
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="fine-print">No completed check is recorded for this source.</p>
                  )}
                </Drawer>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
