import { useQuery } from "@tanstack/react-query";
import { api, dateLabel } from "../api";
import { type Page } from "../types";
import { titleCase, Badge, ErrorNotice, PageHead } from "../components/ui";
import { AddLocation } from "../components/LocationForms";

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
  const access = useQuery({
    queryKey: ["access-log"],
    queryFn: () =>
      api<{
        people: { email: string; role: string; active: boolean; last_seen_at: string | null }[];
        events: { email: string; action: string; method: string | null; at: string }[];
      }>("/api/admin/access-log/"),
  });
  const when = (v: string) =>
    new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZone: "America/New_York",
    }).format(new Date(v));
  const actionText: Record<string, string> = {
    password_login: "Signed in",
    password_login_failed: "Failed sign-in",
    logout: "Signed out",
  };
  return (
    <>
      <PageHead
        eyebrow="Workspace administration"
        title="Keep the workspace reliable."
        description="Problems that need attention, then recorded job activity."
        action={<AddLocation />}
      />
      <section className="panel" aria-labelledby="access-title">
        <h2 id="access-title">Who is using the workspace</h2>
        {access.error ? (
          <ErrorNotice error={access.error} />
        ) : !access.data ? (
          <p className="muted">Loading…</p>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Person</th>
                    <th scope="col">Role</th>
                    <th scope="col">Last active (Eastern)</th>
                  </tr>
                </thead>
                <tbody>
                  {access.data.people.map((p) => (
                    <tr key={p.email}>
                      <td>{p.email}</td>
                      <td>{p.active ? (p.role === "admin" ? "Admin" : "Member") : "Removed"}</td>
                      <td>{p.last_seen_at ? when(p.last_seen_at) : "Never"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details className="area-sources">
              <summary>Recent sign-ins ({access.data.events.length})</summary>
              <ul className="evidence-list">
                {access.data.events.map((e, i) => (
                  <li key={`${i}-${e.at}`}>
                    {when(e.at)} · {e.email} · {actionText[e.action] ?? e.action}
                    {e.method === "email_only" ? " (email)" : e.method === "password" ? " (password)" : ""}
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </section>
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
