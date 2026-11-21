import { ArrowUpRight } from "lucide-react";
import { dateLabel } from "../api";
import { type Source } from "../types";
import { Badge, ErrorNotice, PageHead, Drawer } from "../components/ui";

export function Sources({
  sources,
  error,
}: {
  sources: Source[] | undefined;
  error: unknown;
}) {
  return (
    <>
      <PageHead
        eyebrow="Trust and transparency"
        title="The evidence, explained."
        description="See what each source covers, when it was checked, and where uncertainty remains."
      />
      <p className="notice">
        Map privacy: OpenStreetMap receives your IP and viewed map area when a
        map is open. Property names, notes, and account details stay in this
        workspace.
      </p>
      {error ? (
        <ErrorNotice error={error} />
      ) : !sources ? (
        <p>Loading source coverage…</p>
      ) : (
        <div className="source-grid">
          {sources.map((source) => (
            <section className="panel source-card" key={source.id}>
              <div className="section-heading">
                <span className="eyebrow">{source.provider}</span>
                <Badge
                  tone={
                    source.status === "OK"
                      ? "green"
                      : source.status === "Failing"
                        ? "red"
                        : "amber"
                  }
                >
                  {source.status}
                </Badge>
              </div>
              <h2>{source.name}</h2>
              <p>{source.purpose}</p>
              <span className="small muted">{source.coverage}</span>
              <Drawer
                title={source.name}
                trigger={
                  <button className="text-button">
                    Source details <ArrowUpRight size={15} />
                  </button>
                }
              >
                <dl className="facts">
                  <dt>Provider</dt>
                  <dd>{source.provider}</dd>
                  <dt>Coverage</dt>
                  <dd>{source.coverage}</dd>
                  <dt>Licence</dt>
                  <dd>{source.licence}</dd>
                  <dt>Attribution</dt>
                  <dd>{source.attribution}</dd>
                  <dt>Privacy</dt>
                  <dd>{source.privacy_note}</dd>
                </dl>
                <a
                  className="button secondary"
                  href={source.documentation_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Provider documentation <ArrowUpRight size={16} />
                </a>
                <h3>Recorded checks</h3>
                {source.health_scopes.length ? (
                  source.health_scopes.map((scope) => (
                    <div className="scope-row" key={scope.scope}>
                      <Badge>{scope.status}</Badge>
                      <p>
                        {scope.data_period ?? "No published data period"}
                        <small>
                          Last successful check:{" "}
                          {dateLabel(scope.last_success_at)}
                        </small>
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="notice">
                    No completed check is recorded for this source.
                  </p>
                )}
              </Drawer>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
