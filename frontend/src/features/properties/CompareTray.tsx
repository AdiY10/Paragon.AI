import { X } from "lucide-react";
import { compareHref, MAX_COMPARE } from "../compare/selection";

/** Sticky tray for the compare selection; links to Compare once two or more are chosen. */
export function CompareTray({
  items,
  onRemove,
  onClear,
}: {
  items: { id: string; name: string }[];
  onRemove: (id: string) => void;
  onClear: () => void;
}) {
  if (!items.length) return null;
  const ready = items.length >= 2;
  return (
    <aside className="compare-tray" aria-label="Compare selection">
      <div className="compare-tray-inner">
        <p className="compare-tray-count">
          {items.length} of {MAX_COMPARE} selected
        </p>
        <ul className="compare-chips">
          {items.map((item) => (
            <li key={item.id}>
              <span>{item.name}</span>
              <button type="button" className="chip-remove" aria-label={`Remove ${item.name} from compare`} onClick={() => onRemove(item.id)}>
                <X size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
        <div className="compare-tray-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>
            Clear
          </button>
          {ready ? (
            <a className="btn btn-primary btn-sm" href={compareHref(items.map((i) => i.id))}>
              Compare {items.length} properties
            </a>
          ) : (
            <span className="compare-tray-hint">Choose one more to compare</span>
          )}
        </div>
      </div>
    </aside>
  );
}
