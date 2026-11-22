import { useId } from "react";
import { AttentionBadge } from "../../components/ui/Badge";
import { DEFAULT_DIR, isSortKey, type SortDir, type SortKey } from "../../lib/properties";
import type { Location } from "../../types";
import { AlertsCell, FloodCell, IncomeCell, PeopleCell, SupermarketCell, TrafficCell } from "./cells";
import { CompareCheckbox } from "./CompareCheckbox";

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "attention:asc", label: "Attention (High first)" },
  { value: "name:asc", label: "Name (A–Z)" },
  { value: "state:asc", label: "State (A–Z)" },
  { value: "population:desc", label: "People within 3 mi (most first)" },
  { value: "income:desc", label: "Median household income (highest first)" },
  { value: "aadt:desc", label: "Main-road traffic (most first)" },
  { value: "flood:asc", label: "Flood (inside a zone first)" },
  { value: "supermarket:asc", label: "Nearest supermarket (closest first)" },
  { value: "alerts:desc", label: "Active alerts (most first)" },
];

/** Phone layout (<640 px): one card per property with a "Sort by" select. */
export function PropertyList({
  rows,
  sort,
  dir,
  onSortChange,
  selected,
  full,
  onToggleCompare,
}: {
  rows: Location[];
  sort: SortKey;
  dir: SortDir;
  onSortChange: (key: SortKey, dir: SortDir) => void;
  selected: string[];
  full: boolean;
  onToggleCompare: (id: string) => void;
}) {
  const value = `${sort}:${dir}`;
  const sortId = useId();
  const options = SORT_OPTIONS.some((o) => o.value === value)
    ? SORT_OPTIONS
    : [...SORT_OPTIONS, { value, label: `${sort} (${dir === "asc" ? "ascending" : "descending"})` }];
  return (
    <div className="property-list">
      <div className="field inline">
        <label htmlFor={sortId}>Sort by</label>
        <select
          id={sortId}
          value={value}
          onChange={(event) => {
            const [key, d] = event.target.value.split(":");
            if (isSortKey(key)) onSortChange(key, d === "desc" ? "desc" : d === "asc" ? "asc" : DEFAULT_DIR[key]);
          }}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <ul className="property-cards" aria-label="Owned properties">
        {rows.map((l) => (
          <li key={l.id} className="property-card-m">
            <div className="property-card-m-head">
              <div>
                <a href={"#/p/" + l.id}>{l.name}</a>
                <small>{[l.city, l.state].filter(Boolean).join(", ")}</small>
              </div>
              <AttentionBadge level={l.attention} />
            </div>
            <dl>
              <div>
                <dt>People within 3 mi</dt>
                <dd>
                  <PeopleCell l={l} />
                </dd>
              </div>
              <div>
                <dt>Median household income</dt>
                <dd>
                  <IncomeCell l={l} />
                </dd>
              </div>
              <div>
                <dt>Main-road traffic</dt>
                <dd>
                  <TrafficCell l={l} />
                </dd>
              </div>
              <div>
                <dt>Flood</dt>
                <dd>
                  <FloodCell l={l} />
                </dd>
              </div>
              <div>
                <dt>Nearest supermarket</dt>
                <dd>
                  <SupermarketCell l={l} />
                </dd>
              </div>
              <div>
                <dt>Active alerts</dt>
                <dd>
                  <AlertsCell l={l} />
                </dd>
              </div>
            </dl>
            <div className="property-card-m-compare">
              <CompareCheckbox
                location={l}
                checked={selected.includes(l.id)}
                full={full}
                onToggle={onToggleCompare}
                showText
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
