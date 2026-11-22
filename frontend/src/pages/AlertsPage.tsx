import { useId, useMemo } from "react";
import { useSignals } from "../api/hooks";
import { parseHash, navigate, useQueryState } from "../app/router";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Skeleton } from "../components/ui/Skeleton";
import { AlertGroupItem } from "../features/alerts/AlertGroup";
import { arrange, filterGroups, LEVELS, levelsParam, parseLevels, type Level } from "../features/alerts/grouping";

function setQuery(changes: Record<string, string>) {
  const { path, query } = parseHash(window.location.hash);
  for (const [k, v] of Object.entries(changes)) {
    if (v) query.set(k, v);
    else query.delete(k);
  }
  const q = query.toString();
  navigate(path + (q ? "?" + q : ""), { replace: true });
}

const STATUSES = [
  { value: "active", label: "Active" },
  { value: "dismissed", label: "Dismissed" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "All" },
];

/** `#/alerts`: High and Watch alerts grouped by property (worst first); shared alerts listed once. */
export function AlertsPage() {
  const [levelParam] = useQueryState("level");
  const [status] = useQueryState("status", "active");
  const [category] = useQueryState("category");
  const [property] = useQueryState("property");
  const levels = parseLevels(levelParam);
  const signals = useSignals(status);
  const ids = { status: useId(), category: useId(), property: useId() };
  const groups = signals.data?.groups ?? [];
  const byId = useMemo(() => new Map((signals.data?.results ?? []).map((r) => [r.id, r])), [signals.data]);
  const shown = filterGroups(groups, { levels, category, property });
  const { shared, byProperty } = arrange(shown);
  const categories = [...new Set(groups.map((g) => g.category))].sort();
  const properties = [...new Map(groups.flatMap((g) => g.locations).map((l) => [l.id, l.name])).entries()].sort((a, b) =>
    a[1].localeCompare(b[1]),
  );
  const defaults = !levelParam && status === "active" && !category && !property;
  const toggleLevel = (level: Level, on: boolean) => {
    const next = on ? [...levels, level] : levels.filter((l) => l !== level);
    setQuery({ level: next.length ? levelsParam(LEVELS.filter((l) => next.includes(l))) : "none" });
  };
  const levelChecked = (level: Level) => (levelParam === "none" ? false : levels.includes(level));
  const effectiveLevels = levelParam === "none" ? [] : levels;
  const visible = effectiveLevels.length ? { shared, byProperty } : { shared: [], byProperty: [] };
  const count = visible.shared.length + visible.byProperty.reduce((n, b) => n + b.groups.length, 0);
  return (
    <div className="alerts-page">
      <header className="page-header">
        <h1>Alerts</h1>
        <p className="page-lead">
          Changes worth acting on at your properties. Each alert says what changed, where the figure comes from, and a next
          step.
        </p>
      </header>
      <div className="alerts-filters" role="search" aria-label="Filter alerts">
        <fieldset className="level-filter">
          <legend>Level</legend>
          {LEVELS.map((level) => (
            <label key={level}>
              <input type="checkbox" checked={levelChecked(level)} onChange={(e) => toggleLevel(level, e.target.checked)} />
              {level === "FYI" ? "FYI" : level}
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor={ids.status}>Status</label>
          <select id={ids.status} value={status} onChange={(e) => setQuery({ status: e.target.value === "active" ? "" : e.target.value })}>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.category}>Category</label>
          <select id={ids.category} value={category} onChange={(e) => setQuery({ category: e.target.value })}>
            <option value="">Any category</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.property}>Property</label>
          <select id={ids.property} value={property} onChange={(e) => setQuery({ property: e.target.value })}>
            <option value="">All properties</option>
            {properties.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <p className="result-count" role="status">
          {signals.data ? `${count} ${count === 1 ? "alert" : "alerts"}` : ""}
        </p>
      </div>
      {signals.error ? (
        <ErrorState error={signals.error} title="Alerts could not load." onRetry={() => void signals.refetch()} />
      ) : !signals.data ? (
        <Skeleton lines={5} height={48} />
      ) : count === 0 ? (
        <EmptyState title={defaults ? "No High or Watch alerts." : "No alerts match these filters."}>
          {defaults
            ? "Alerts appear here when public data shows a change worth acting on at one of your properties."
            : "Change the filters to see more."}
        </EmptyState>
      ) : (
        <>
          {visible.shared.length > 0 && (
            <section className="alert-bucket" aria-labelledby="shared-alerts">
              <h2 id="shared-alerts">Shared by several properties</h2>
              <ul className="alert-items">
                {visible.shared.map((g) => (
                  <AlertGroupItem key={g.key} group={g} signal={byId.get(g.signal_ids[0])} shared />
                ))}
              </ul>
            </section>
          )}
          {visible.byProperty.map((bucket) => (
            <section key={bucket.location.id} className="alert-bucket" aria-labelledby={"alerts-" + bucket.location.id}>
              <h2 id={"alerts-" + bucket.location.id}>
                <a href={"#/p/" + bucket.location.id}>{bucket.location.name}</a>
                <small>{[bucket.location.city, bucket.location.state].filter(Boolean).join(", ")}</small>
              </h2>
              <ul className="alert-items">
                {bucket.groups.map((g) => (
                  <AlertGroupItem key={g.key} group={g} signal={byId.get(g.signal_ids[0])} shared={false} />
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
