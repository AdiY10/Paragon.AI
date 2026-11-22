import type { SignalGroup, SignalsResponse } from "../../api/types";
import { AttentionBadge, Badge } from "../../components/ui/Badge";
import { dateLabel } from "../../lib/format/dates";
import { sourceName } from "../../lib/format/sources";
import { AlertEvidence, type AlertLike } from "./AlertEvidence";
import { RULE_NAMES } from "./alertText";

type Result = SignalsResponse["results"][number];

/** One alert (or one shared alert for several properties): level, what changed, next step, evidence. */
export function AlertGroupItem({ group, signal, shared }: { group: SignalGroup; signal: Result | undefined; shared: boolean }) {
  const alert: AlertLike = signal
    ? { ...signal, feedback: signal.feedback ?? undefined, next_step: group.next_step }
    : {
        id: group.signal_ids[0],
        rule_id: group.rule_id,
        title: group.title,
        severity: group.severity,
        why: group.why,
        period: group.period,
        source: group.source,
        evidence: group.evidence,
        status: group.status,
        next_step: group.next_step,
      };
  const names = group.locations.map((l) => l.name);
  return (
    <li className="alert-item">
      <div className="alert-level">
        {group.severity === "FYI" ? <Badge>FYI</Badge> : <AttentionBadge level={group.severity} />}
      </div>
      <div className="alert-body">
        <p className="alert-title">{group.title}</p>
        <p className="alert-why">{group.why}</p>
        {group.next_step && (
          <p className="next-step">
            <strong>Next step:</strong> {group.next_step}
          </p>
        )}
        {shared && (
          <p className="alert-properties">
            Applies to {names.length} properties:{" "}
            {group.locations.map((l, i) => (
              <span key={l.id}>
                {i > 0 && ", "}
                <a href={"#/p/" + l.id}>{l.name}</a>
              </span>
            ))}
          </p>
        )}
        <p className="alert-meta">
          {[
            RULE_NAMES[group.rule_id] ?? group.category,
            sourceName(group.source),
            group.period,
            signal?.detected_at ? `since ${dateLabel(signal.detected_at)}` : null,
            group.status !== "active" ? group.status : signal?.reviewed ? "reviewed" : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <AlertEvidence alert={alert} applyToGroup={shared} properties={shared ? names : undefined} />
      </div>
    </li>
  );
}
