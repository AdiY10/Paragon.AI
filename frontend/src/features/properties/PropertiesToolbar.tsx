import { useId } from "react";
import { Search, X } from "lucide-react";
import { ATTENTION_LEVELS } from "../../lib/properties";

/** Search, State, Attention, Clear filters and the result count. Every value lives in the URL. */
export function PropertiesToolbar({
  q,
  state,
  attention,
  states,
  shown,
  total,
  onChange,
  onClear,
}: {
  q: string;
  state: string;
  attention: string;
  states: string[];
  shown: number;
  total: number;
  onChange: (key: "q" | "state" | "attention", value: string) => void;
  onClear: () => void;
}) {
  const filtered = !!(q || state || attention);
  const stateId = useId(),
    attentionId = useId();
  return (
    <div className="properties-toolbar" role="search" aria-label="Filter properties">
      <label className="field search-field">
        <span className="sr-only">Search properties</span>
        <Search size={16} aria-hidden="true" className="field-icon" />
        <input
          type="search"
          placeholder="Search properties"
          value={q}
          maxLength={100}
          autoComplete="off"
          onChange={(event) => onChange("q", event.target.value)}
        />
      </label>
      <div className="field">
        <label htmlFor={stateId}>State</label>
        <select id={stateId} value={state} onChange={(event) => onChange("state", event.target.value)}>
          <option value="">All states</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={attentionId}>Attention</label>
        <select id={attentionId} value={attention} onChange={(event) => onChange("attention", event.target.value)}>
          <option value="">Any attention</option>
          {ATTENTION_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
      </div>
      <button type="button" className="btn btn-ghost btn-sm clear-filters" onClick={onClear} disabled={!filtered}>
        <X size={14} aria-hidden="true" /> Clear filters
      </button>
      <p className="result-count" role="status">
        {filtered ? `Showing ${shown} of ${total}` : `${total} properties`}
      </p>
    </div>
  );
}
