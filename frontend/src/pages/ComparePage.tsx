import { useId, useState } from "react";
import { Printer, X } from "lucide-react";
import { useCompare, useLocations } from "../api/hooks";
import { navigate, parseHash } from "../app/router";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Skeleton } from "../components/ui/Skeleton";
import { CompareTable, type CompareData } from "../features/compare/CompareTable";
import { MAX_COMPARE, parseIds, readSelection, writeSelection } from "../features/compare/selection";

/** `#/compare?ids=`: up to four owned properties or analyzed places side by side. */
export function ComparePage() {
  // ?ids= wins (links from the Properties tray); otherwise the stored selection.
  const [ids, setIds] = useState(() => {
    const fromUrl = parseIds(parseHash(window.location.hash).query.get("ids"));
    return fromUrl.length ? fromUrl : readSelection();
  });
  const pickerId = useId();
  const all = useLocations();
  const data = useCompare<CompareData>(ids);
  const update = (next: string[]) => {
    writeSelection(next);
    setIds(next);
    navigate(next.length ? "/compare?ids=" + next.join(",") : "/compare", { replace: true });
  };
  const records = all.data ?? [];
  const byId = new Map(records.map((l) => [l.id, l]));
  const available = records.filter((l) => l.status !== "archived" && !ids.includes(l.id) && l.current_revision.lat !== null);
  const owned = available.filter((l) => l.status === "owned").sort((a, b) => a.name.localeCompare(b.name));
  const places = available.filter((l) => l.screening).sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <div className="compare-page">
      <header className="page-header">
        <h1>Compare</h1>
        <p className="page-lead">Up to four properties or analyzed places side by side, with your portfolio's median and range.</p>
      </header>
      <div className="compare-picker-v2">
        <ul className="compare-chips" aria-label="Compared">
          {ids.map((id) => {
            const name = byId.get(id)?.name ?? "Location";
            return (
              <li key={id}>
                <span>{name}</span>
                <button type="button" className="chip-remove" aria-label={`Remove ${name}`} onClick={() => update(ids.filter((x) => x !== id))}>
                  <X size={14} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
        {ids.length < MAX_COMPARE ? (
          <div className="field">
            <label htmlFor={pickerId}>Add to the comparison</label>
            <select id={pickerId} value="" onChange={(e) => e.target.value && update([...ids, e.target.value])}>
              <option value="">Choose a property or place…</option>
              <optgroup label="Properties">
                {owned.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({[l.city, l.state].filter(Boolean).join(", ")})
                  </option>
                ))}
              </optgroup>
              {places.length > 0 && (
                <optgroup label="Analyzed places">
                  {places.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>
        ) : (
          <p className="fine-print">Up to 4. Remove one to add another.</p>
        )}
      </div>
      {ids.length < 2 ? (
        <EmptyState title="Choose at least two to compare.">
          Tick "Compare" next to properties on the Properties page, use Compare on any analysis, or add them here.
        </EmptyState>
      ) : data.error ? (
        <ErrorState error={data.error} title="The comparison could not load." onRetry={() => void data.refetch()} />
      ) : !data.data ? (
        <Skeleton lines={8} height={28} />
      ) : (
        <>
          <CompareTable data={data.data} />
          <p className="fine-print">{data.data.note}</p>
          <div>
            <Button variant="secondary" size="sm" onClick={() => window.print()}>
              <Printer size={14} aria-hidden="true" /> Print or save as PDF
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
