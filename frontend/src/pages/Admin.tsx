import { useQuery } from "@tanstack/react-query";
import { api, dateLabel } from "../api";
import { type Page } from "../types";
import { titleCase, Badge, ErrorNotice, PageHead } from "../components/ui";

export function Admin() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () =>
      api<
        Page<{
          id: string;
          kind: string;
          status: string;
          records: number;
          failed_items: number;
          error_code: string;
          created_at: string;
        }>
      >("/api/admin/jobs/"),
  });
  const alerts = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: () =>
      api<{
        open: { key: string; summary: string; count: number; first_at: string; last_at: string }[];
        resolved: { key: string; summary: string; resolved_at: string }[];
      }>("/api/admin/alerts/"),
  });
  return (
    <>
      <PageHead
        eyebrow="Workspace administration"
        title="Keep the workspace reliable."
        description="Problems that need attention, then recorded job activity."
      />
      <section className="panel" aria-labelledby="alerts-title">
        <h2 id="alerts-title">Open alerts</h2>
        {alerts.error ? (
          <ErrorNotice error={alerts.error} />
        ) : !alerts.data ? (
          <p className="muted">Loading alerts…</p>
        ) : alerts.data.open.length === 0 ? (
          <p className="muted">No open alerts. Data refreshes and sources are working.</p>
        ) : (
          <ul className="change-list">
            {alerts.data.open.map((a) => (
              <li key={a.key}>
                <span className="badge red">Alert</span>
                <div>
                  <strong>{a.summary}</strong>
                  <small>
                    {a.count} occurrence{a.count === 1 ? "" : "s"} · first {dateLabel(a.first_at)} · latest{" "}
                    {dateLabel(a.last_at)}
                  </small>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <h2>Recent job runs</h2>
        {jobs.error ? (
          <ErrorNotice error={jobs.error} />
        ) : jobs.isPending ? (
          <p className="muted">Loading recorded job activity…</p>
        ) : jobs.data?.results.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Done</th>
                  <th>Failed</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.results.map((job) => (
                  <tr key={job.id}>
                    <td>{titleCase(job.kind)}</td>
                    <td>
                      <Badge tone={job.status === "failed" ? "red" : job.status === "succeeded" ? "green" : "neutral"}>
                        {titleCase(job.status)}
                        {job.error_code ? ` · ${job.error_code}` : ""}
                      </Badge>
                    </td>
                    <td>{job.records}</td>
                    <td>{job.failed_items || "—"}</td>
                    <td>{dateLabel(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No job runs are recorded yet.</p>
        )}
      </section>
    </>
  );
}
