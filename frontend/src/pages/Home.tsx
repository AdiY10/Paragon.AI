import { ArrowRight } from "lucide-react";
import ThisWeek from "../ThisWeek";
import { type Location, type Source } from "../types";
import { Badge } from "../components/ui";
import { rankAttention } from "./Portfolio";

export function Overview({
  locations,
  isAdmin,
}: {
  locations: Location[];
  sources: Source[];
  isAdmin: boolean;
}) {
  const owned = locations.filter((l) => l.status === "owned");
  const counts = { High: 0, Watch: 0, Clear: 0 };
  for (const l of owned) counts[(l.attention ?? "Clear") as keyof typeof counts] += 1;
  const unconfirmed = owned.filter((l) => !l.confirmed).length,
    missing = owned.filter((l) => l.current_revision.lat === null).length;
  const flagged = owned
    .filter((l) => l.attention === "High" || l.attention === "Watch")
    .sort((a, b) => rankAttention(a) - rankAttention(b) || a.name.localeCompare(b.name));
  return (
    <>
      <ThisWeek isAdmin={isAdmin} lead />
      <section className="panel health" aria-labelledby="health-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PORTFOLIO HEALTH</span>
            <h2 id="health-title">{owned.length} owned properties</h2>
          </div>
          <a className="text-button" href="#/portfolio">
            Open portfolio <ArrowRight size={15} />
          </a>
        </div>
        <div className="health-strip">
          {(["High", "Watch", "Clear"] as const).map((level) => (
            <a key={level} className={`health-tile ${level.toLowerCase()}`} href={`#/portfolio?attention=${level}`}>
              <strong>{counts[level]}</strong>
              <span>{level === "Clear" ? "No attention needed" : `${level} attention`}</span>
            </a>
          ))}
        </div>
        {flagged.length > 0 && (
          <ul className="flagged-list" aria-label="Properties that need attention">
            {flagged.slice(0, 8).map((l) => (
              <li key={l.id}>
                <Badge tone={l.attention === "High" ? "red" : "amber"}>{l.attention}</Badge>
                <a href={"#/locations/" + l.id}>{l.name}</a>
                <small>
                  {l.city}, {l.state}
                </small>
              </li>
            ))}
          </ul>
        )}
      </section>
      {(unconfirmed > 0 || missing > 0) && (
        <section className="panel setup-note" aria-labelledby="setup-title">
          <h2 id="setup-title">Setup</h2>
          <p className="muted">
            {unconfirmed > 0 && `${unconfirmed} properties still need you to confirm they are owned. `}
            {missing > 0 && `${missing} need a map pin before area data can be computed.`}
          </p>
          <a className="button small-button" href="#/setup">
            Confirm your portfolio <ArrowRight size={15} />
          </a>
        </section>
      )}
    </>
  );
}
