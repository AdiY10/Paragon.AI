import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { AttentionBadge } from "../../components/ui/Badge";
import type { SortDir, SortKey } from "../../lib/properties";
import type { Location } from "../../types";
import { AlertsCell, FloodCell, IncomeCell, PeopleCell, SupermarketCell, TrafficCell } from "./cells";
import { CompareCheckbox } from "./CompareCheckbox";

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "state", label: "State" },
  { key: "attention", label: "Attention" },
  { key: "population", label: "People within 3 mi", numeric: true },
  { key: "income", label: "Median household income", numeric: true },
  { key: "aadt", label: "Main-road traffic", numeric: true },
  { key: "flood", label: "Flood" },
  { key: "supermarket", label: "Nearest supermarket" },
  { key: "alerts", label: "Active alerts", numeric: true },
];

function SortHeader({
  column,
  sort,
  dir,
  onSort,
  numeric,
  className,
}: {
  column: { key: SortKey; label: string };
  sort: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
  numeric?: boolean;
  className?: string;
}) {
  const active = sort === column.key;
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      className={[numeric ? "num" : "", className ?? ""].join(" ").trim() || undefined}
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : undefined}
    >
      <button type="button" className="sort-button" onClick={() => onSort(column.key)}>
        {column.label}
        <Icon size={13} aria-hidden="true" className={active ? "sort-icon active" : "sort-icon"} />
      </button>
    </th>
  );
}

/** The owned-property table (≥640 px). Row hover/focus highlights the pin on the map. */
export function PropertiesTable({
  rows,
  sort,
  dir,
  onSort,
  selected,
  full,
  onToggleCompare,
  highlightId,
  onHighlight,
  id,
}: {
  rows: Location[];
  sort: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
  selected: string[];
  full: boolean;
  onToggleCompare: (id: string) => void;
  highlightId: string | null;
  onHighlight: (id: string | null) => void;
  id: string;
}) {
  return (
    <div className="table-scroll" role="region" aria-labelledby={id + "-caption"} tabIndex={0}>
      <table className="properties-table" id={id}>
        <caption id={id + "-caption"}>Owned properties</caption>
        <thead>
          <tr>
            <th scope="col" className="col-compare sticky-1">
              <span className="sr-only">Compare</span>
            </th>
            <SortHeader
              column={{ key: "name", label: "Property" }}
              sort={sort}
              dir={dir}
              onSort={onSort}
              className="col-name sticky-2"
            />
            {COLUMNS.map((column) => (
              <SortHeader key={column.key} column={column} sort={sort} dir={dir} onSort={onSort} numeric={column.numeric} />
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => (
            <tr
              key={l.id}
              className={highlightId === l.id ? "is-highlighted" : undefined}
              onPointerEnter={() => onHighlight(l.id)}
              onPointerLeave={() => onHighlight(null)}
              onFocus={() => onHighlight(l.id)}
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node)) onHighlight(null);
              }}
            >
              <td className="col-compare sticky-1">
                <CompareCheckbox location={l} checked={selected.includes(l.id)} full={full} onToggle={onToggleCompare} />
              </td>
              <th scope="row" className="col-name sticky-2">
                <a href={"#/p/" + l.id}>{l.name}</a>
                <small>{l.city || l.address}</small>
              </th>
              <td>{l.state || "—"}</td>
              <td>
                <AttentionBadge level={l.attention} />
              </td>
              <td className="num">
                <PeopleCell l={l} />
              </td>
              <td className="num">
                <IncomeCell l={l} />
              </td>
              <td className="num">
                <TrafficCell l={l} />
              </td>
              <td>
                <FloodCell l={l} />
              </td>
              <td>
                <SupermarketCell l={l} />
              </td>
              <td className="num">
                <AlertsCell l={l} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
