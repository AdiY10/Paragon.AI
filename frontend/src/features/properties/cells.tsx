/** Shared cell renderers for the table and the phone card list. Missing → "—" + hidden "Unavailable". */
import { distanceMi, floodShort, formatIncome, formatInt } from "../../lib/format/numbers";
import { Missing } from "../../components/ui/Stat";
import type { Location } from "../../types";

type K = NonNullable<Location["key_numbers"]>;
const numbers = (l: Location): K => l.key_numbers ?? {};

export const PeopleCell = ({ l }: { l: Location }) => <>{formatInt(numbers(l).population) ?? <Missing />}</>;
export const IncomeCell = ({ l }: { l: Location }) => (
  <>{formatIncome(numbers(l).median_household_income) ?? <Missing />}</>
);
export function TrafficCell({ l }: { l: Location }) {
  const aadt = formatInt(numbers(l).aadt);
  return aadt ? (
    <>
      {aadt}
      <span className="unit">/day</span>
    </>
  ) : (
    <Missing />
  );
}
export function FloodCell({ l }: { l: Location }) {
  const flood = numbers(l).flood;
  const text = floodShort(flood);
  if (!text) return <Missing />;
  return <span className={flood === "inside" ? "flood-flag inside" : "flood-flag"}>{text}</span>;
}
export function SupermarketCell({ l }: { l: Location }) {
  const s = numbers(l).nearest_supermarket;
  if (!s) return <Missing />;
  return (
    <>
      {s.name}
      <span className="unit"> · {distanceMi(s.distance_mi)}</span>
    </>
  );
}
export function AlertsCell({ l }: { l: Location }) {
  const count = numbers(l).active_alerts;
  if (count === null || count === undefined) return <Missing />;
  if (count === 0) return <>0</>;
  return (
    <a href={`#/alerts?property=${l.id}`} aria-label={`${count} active ${count === 1 ? "alert" : "alerts"} for ${l.name}`}>
      {count}
    </a>
  );
}
